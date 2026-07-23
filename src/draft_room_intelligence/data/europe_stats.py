"""Normalize official Swedish, Finnish, and cached Russian league statistics."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from draft_room_intelligence.data.chl_stats import (
    count_normalized_names,
    normalize_person_key,
    read_drafted_league_hints,
    read_table,
)
from draft_room_intelligence.data.eliteprospects_csv import (
    ADVANCED_STAT_LINE_COLUMNS,
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name

EUROPE_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "match_method",
    "provider",
    "league",
    "source_name",
    "source_id",
    "source_url",
    "team",
    "games",
    "points",
    "save_percentage",
]

LEAGUE_FAMILIES = {
    "sweden": {"SHL", "HockeyAllsvenskan", "Sweden Jrs."},
    "finland": {"Liiga", "Mestis", "Finland Jrs."},
    "russia": {"KHL", "VHL", "MHL"},
}

COUNTRY_LEAGUE_FAMILIES = {
    "SWEDEN": "sweden",
    "FINLAND": "finland",
    "RUSSIA": "russia",
}

CYRILLIC_TRANSLITERATION = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)
RUSSIAN_FIRST_NAME_EQUIVALENTS = {
    "aleksandr": "alexander",
    "aleksey": "alexei",
    "aleksei": "alexei",
    "artem": "artyom",
    "egor": "yegor",
    "semen": "semyon",
}


@dataclass(frozen=True)
class EuropeStatSource:
    season: str
    provider: str
    league: str
    source_url: str
    regular_season: bool = True
    kind: str = "combined"
    source_path: Path | None = None


@dataclass(frozen=True)
class EuropeStatLine:
    name: str
    source_id: str
    source_url: str
    provider: str
    league: str
    season: str
    regular_season: bool
    team: str
    games: str
    goals: str = ""
    assists: str = ""
    points: str = ""
    goalie_minutes: str = ""
    saves: str = ""
    goals_against: str = ""
    save_percentage: str = ""
    goals_against_average: str = ""
    wins: str = ""
    losses: str = ""
    ties: str = ""
    shutouts: str = ""
    plus_minus: str = ""
    shots: str = ""
    blocks: str = ""
    faceoff_wins: str = ""
    faceoff_losses: str = ""
    faceoff_percentage: str = ""


@dataclass(frozen=True)
class EuropeStatsEnrichmentSummary:
    players_scanned: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    output_advanced_lines: int
    match_report_path: Path


def enrich_europe_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    sources: list[EuropeStatSource],
) -> EuropeStatsEnrichmentSummary:
    source_root = Path(base_dir)
    target_root = Path(output_dir)
    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    players = read_table(source_root / "players.csv")
    base_stats = read_table(source_root / "season_stat_lines.csv")
    advanced_path = source_root / "advanced_stat_lines.csv"
    base_advanced = read_table(advanced_path) if advanced_path.is_file() else []
    drafted_leagues = read_drafted_league_hints(source_root)
    source_lines = load_europe_source_lines(sources)
    configured_families = {
        {"swehockey": "sweden", "liiga": "finland", "khl": "russia"}[source.provider]
        for source in sources
    }
    by_name: dict[str, list[EuropeStatLine]] = {}
    for line in source_lines:
        for key in person_identity_keys(line.name):
            by_name.setdefault(key, []).append(line)

    name_counts = count_normalized_names(players)
    matched: dict[str, list[EuropeStatLine]] = {}
    report: list[dict[str, str]] = []
    for player in players:
        player_id = player["player_id"]
        leagues = {
            normalize_league_name(row.get("league", ""))
            for row in base_stats
            if row.get("player_id") == player_id
        }
        leagues.update(drafted_leagues.get(player_id, set()))
        keys = person_identity_keys(player["name"])
        exact_key = normalize_person_key(player["name"])
        candidates = deduplicate_source_lines(
            line
            for key in keys
            for line in by_name.get(key, [])
            if same_league_family(leagues, line)
        )
        match_method = (
            "exact_name"
            if any(normalize_person_key(line.name) == exact_key for line in candidates)
            else "transliterated_name"
        )
        if name_counts.get(exact_key) == 1 and candidates:
            matched[player_id] = candidates
            report.extend(build_match_row(player, line, True, match_method) for line in candidates)
        else:
            applicable = any(
                leagues_match_family(leagues, family) for family in configured_families
            )
            report.append(
                build_match_row(
                    player,
                    None,
                    False,
                    "unmatched" if applicable else "not_configured",
                )
            )

    candidate_keys = {
        (player_id, line.season, line.league, line.regular_season)
        for player_id, lines in matched.items()
        for line in lines
    }
    existing_games: dict[tuple[str, str, str, bool], int] = {}
    existing_sources: dict[tuple[str, str, str, bool], set[str]] = {}
    for row in base_stats:
        key = stat_key(row)
        if key in candidate_keys:
            existing_games[key] = max(existing_games.get(key, 0), integer(row.get("games", "")))
            existing_sources.setdefault(key, set()).add(row.get("source", ""))
    candidate_providers = {
        key: {
            line.provider
            for player_id, lines in matched.items()
            for line in lines
            if (player_id, line.season, line.league, line.regular_season) == key
        }
        for key in candidate_keys
    }
    full_replacement_keys = {
        key
        for key in candidate_keys
        if max(
            integer(line.games)
            for player_id, lines in matched.items()
            for line in lines
            if (player_id, line.season, line.league, line.regular_season) == key
        )
        >= existing_games.get(key, 0)
    }
    provider_correction_keys = {
        key
        for key in candidate_keys - full_replacement_keys
        if any(
            source_contains_provider(source, provider)
            for source in existing_sources.get(key, set())
            for provider in candidate_providers[key]
        )
    }
    advanced_candidate_keys = {
        (player_id, line.season, line.league, line.regular_season)
        for player_id, lines in matched.items()
        for line in lines
        if has_advanced_stats(line)
    }
    output_stats = [
        row
        for row in base_stats
        if stat_key(row) not in full_replacement_keys
        and not (
            stat_key(row) in provider_correction_keys
            and row.get("source", "") in candidate_providers[stat_key(row)]
        )
    ]
    output_advanced = [
        row for row in base_advanced if stat_key(row) not in advanced_candidate_keys
    ]
    for player_id, lines in sorted(matched.items()):
        output_stats.extend(
            build_stat_line(player_id, line)
            for line in lines
            if (player_id, line.season, line.league, line.regular_season)
            in full_replacement_keys | provider_correction_keys
        )
        output_advanced.extend(
            build_advanced_line(player_id, line) for line in lines if has_advanced_stats(line)
        )

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stats)
    write_table(
        target_root / "advanced_stat_lines.csv", ADVANCED_STAT_LINE_COLUMNS, output_advanced
    )
    write_table(target_root / "europe_stat_matches.csv", EUROPE_MATCH_COLUMNS, report)
    return EuropeStatsEnrichmentSummary(
        len(players),
        len(source_lines),
        len(matched),
        len(output_stats),
        len(output_advanced),
        target_root / "europe_stat_matches.csv",
    )


def load_europe_source_lines(sources: list[EuropeStatSource]) -> list[EuropeStatLine]:
    lines: list[EuropeStatLine] = []
    for source in sources:
        if source.source_path is None:
            raise ValueError("European source requires a collected cache")
        raw = source.source_path.read_text(encoding="utf-8")
        if source.provider == "swehockey":
            lines.extend(parse_swehockey(raw, source))
        elif source.provider == "liiga":
            lines.extend(parse_liiga(raw, source))
        elif source.provider == "khl":
            lines.extend(parse_khl_html(raw, source))
        else:
            raise ValueError(f"unsupported European provider: {source.provider}")
    return lines


class HtmlTableParser(HTMLParser):
    def __init__(self, table_class: str | None = None) -> None:
        super().__init__()
        self.table_class = table_class
        self.table_depth = 0
        self.target_depth = 0
        self.in_cell = False
        self.cell: list[str] = []
        self.href = ""
        self.row: list[tuple[str, str]] = []
        self.table: list[list[tuple[str, str]]] = []
        self.tables: list[list[list[tuple[str, str]]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self.table_depth += 1
            classes = (attributes.get("class") or "").split()
            if not self.target_depth and (self.table_class is None or self.table_class in classes):
                self.target_depth = self.table_depth
                self.table = []
        elif self.target_depth and tag in {"th", "td"}:
            self.in_cell = True
            self.cell = []
            self.href = ""
        elif self.in_cell and tag == "a":
            self.href = attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.target_depth and tag in {"th", "td"} and self.in_cell:
            value = re.sub(r"\s+", " ", "".join(self.cell)).strip()
            self.row.append((value, self.href))
            self.in_cell = False
        elif self.target_depth and tag == "tr" and self.table_depth == self.target_depth:
            if self.row:
                self.table.append(self.row)
            self.row = []
        elif tag == "table":
            if self.target_depth == self.table_depth:
                if self.table:
                    self.tables.append(self.table)
                self.target_depth = 0
                self.table = []
                self.row = []
            self.table_depth -= 1


def parse_swehockey(raw: str, source: EuropeStatSource) -> list[EuropeStatLine]:
    parser = HtmlTableParser("tblContent")
    parser.feed(raw)
    lines: list[EuropeStatLine] = []
    current_team = ""
    for table in parser.tables:
        section = ""
        headers: list[str] = []
        for row in table:
            values = [cell[0] for cell in row]
            if values and values[0] in {"Playing Statistics", "Goalkeeping Statistics"}:
                section = values[0]
                headers = []
            elif "Name" in values and ({"GP", "TP"} & set(values) or "GPI" in values):
                headers = values
            elif not section and not headers and values and values[0]:
                current_team = values[0].removesuffix("[Top]").strip()
            elif headers and (line := swehockey_row(headers, row, current_team, section, source)):
                lines.append(line)
    if not lines:
        raise ValueError("Swehockey payload has no player statistics")
    return lines


def swehockey_row(
    headers: list[str],
    row: list[tuple[str, str]],
    team: str,
    section: str,
    source: EuropeStatSource,
) -> EuropeStatLine | None:
    values = {
        header: row[index][0] if index < len(row) else "" for index, header in enumerate(headers)
    }
    name = display_swedish_name(values.get("Name", ""))
    if not name:
        return None
    common = (
        name,
        normalize_person_key(name),
        source.source_url,
        source.provider,
        source.league,
        source.season,
        source.regular_season,
        team,
    )
    if section == "Goalkeeping Statistics":
        return EuropeStatLine(
            *common,
            values.get("GPI", ""),
            goalie_minutes=values.get("MIP", ""),
            saves=values.get("SVS", ""),
            goals_against=values.get("GA", ""),
            save_percentage=percent_to_decimal(values.get("SVS%", "")),
            goals_against_average=values.get("GAA", ""),
            wins=values.get("W", ""),
            losses=values.get("L", ""),
            shutouts=values.get("SO", ""),
        )
    return EuropeStatLine(
        *common,
        values.get("GP", ""),
        values.get("G", ""),
        values.get("A", ""),
        values.get("TP", ""),
        plus_minus=values.get("+/-", ""),
        shots=values.get("SOG", ""),
        faceoff_wins=values.get("FO+", ""),
        faceoff_losses=values.get("FO-", ""),
        faceoff_percentage=values.get("FO%", ""),
    )


def parse_liiga(raw: str, source: EuropeStatSource) -> list[EuropeStatLine]:
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Liiga payload must be a player list")
    lines = [line for row in payload if isinstance(row, dict) if (line := liiga_row(row, source))]
    if not lines:
        raise ValueError("Liiga payload has no player statistics")
    return lines


def liiga_row(row: dict[str, object], source: EuropeStatSource) -> EuropeStatLine | None:
    name = " ".join(str(row.get(field, "")).strip() for field in ("firstName", "lastName")).strip()
    games = row.get("playedGames", row.get("games"))
    if not name or not games:
        return None
    common = (
        name,
        str(row.get("playerId", normalize_person_key(name))),
        source.source_url,
        source.provider,
        source.league,
        source.season,
        source.regular_season,
        str(row.get("teamName", "")),
        str(games),
    )
    if source.kind == "goalies" or row.get("goalkeeper") is True:
        return EuropeStatLine(
            *common,
            goalie_minutes=seconds_to_minutes_text(row.get("timeOnIce")),
            saves=value(row, "blockedOrSavedShots"),
            goals_against=value(row, "goalsAgainst"),
            save_percentage=normalize_save_percentage(row.get("savePercentage")),
            goals_against_average=value(row, "goalsAgainstAvg"),
            wins=value(row, "gkWins"),
            losses=value(row, "gkLosses"),
            ties=value(row, "gkTies"),
            shutouts=value(row, "shutOut"),
        )
    return EuropeStatLine(
        *common,
        goals=value(row, "goals"),
        assists=value(row, "assists"),
        points=value(row, "points"),
        plus_minus=value(row, "plusMinus"),
        shots=value(row, "shots"),
        faceoff_wins=value(row, "contestWon"),
        faceoff_losses=value(row, "contestLost"),
        faceoff_percentage=value(row, "contestWonPercentage"),
    )


def parse_khl_html(raw: str, source: EuropeStatSource) -> list[EuropeStatLine]:
    parser = HtmlTableParser()
    parser.feed(raw)
    profile_lines = parse_khl_player_profile(raw, parser.tables, source)
    if profile_lines:
        return profile_lines

    lines: list[EuropeStatLine] = []
    for table in parser.tables:
        header_index = next(
            (index for index, row in enumerate(table) if "Player" in [cell[0] for cell in row]),
            -1,
        )
        if header_index < 0:
            continue
        headers = [cell[0] for cell in table[header_index]]
        for row in table[header_index + 1 :]:
            values = {
                header: row[index][0] if index < len(row) else ""
                for index, header in enumerate(headers)
            }
            name = values.get("Player", "")
            if not name or not values.get("GP"):
                continue
            lines.append(
                EuropeStatLine(
                    name,
                    normalize_person_key(name),
                    source.source_url,
                    source.provider,
                    source.league,
                    source.season,
                    source.regular_season,
                    values.get("Team", ""),
                    values.get("GP", ""),
                    values.get("G", ""),
                    values.get("A", values.get("Assists", "")),
                    values.get("PTS", ""),
                    plus_minus=values.get("+/-", ""),
                )
            )
    if not lines:
        raise ValueError("KHL-family payload has no complete player statistics table")
    return lines


def parse_khl_player_profile(
    raw: str,
    tables: list[list[list[tuple[str, str]]]],
    source: EuropeStatSource,
) -> list[EuropeStatLine]:
    name = khl_profile_name(raw)
    if not name:
        return []
    source_id_match = re.search(r"/players/(\d+)", source.source_url)
    source_id = source_id_match.group(1) if source_id_match else normalize_person_key(name)
    lines: list[EuropeStatLine] = []
    for table in tables:
        header_index = next(
            (
                index
                for index, row in enumerate(table)
                if row and re.fullmatch(r"Турнир\s*/\s*(?:Команда|Клуб)", row[0][0])
            ),
            -1,
        )
        if header_index < 0:
            continue
        headers = [cell[0] for cell in table[header_index]]
        season = ""
        regular_season = source.regular_season
        for row in table[header_index + 1 :]:
            marker = row[0][0] if row else ""
            season_match = re.match(r"(\d{2})/(\d{2})\s*\|\s*(.+)", marker)
            if season_match:
                season = f"20{season_match.group(1)}-{season_match.group(2)}"
                regular_season = "регуляр" in season_match.group(3).casefold()
                continue
            if not season or len(row) < len(headers) or marker.startswith("Суммарная"):
                continue
            values = {
                header: row[index][0] if index < len(row) else ""
                for index, header in enumerate(headers)
            }
            games = values.get("И", "")
            if not games or not marker:
                continue
            if "%ОБ" in headers:
                lines.append(
                    EuropeStatLine(
                        name,
                        source_id,
                        source.source_url,
                        source.provider,
                        source.league,
                        season,
                        regular_season,
                        marker,
                        games,
                        goals=values.get("Ш", ""),
                        assists=values.get("А", ""),
                        goalie_minutes=values.get("ВП", ""),
                        saves=values.get("ОБ", ""),
                        goals_against=values.get("ПШ", ""),
                        save_percentage=percent_to_decimal(values.get("%ОБ", "")),
                        goals_against_average=values.get("КН", ""),
                        wins=values.get("В", ""),
                        losses=values.get("П", ""),
                        shutouts=values.get('И"0"', ""),
                    )
                )
                continue
            faceoff_attempts = integer(values.get("Вбр", ""))
            faceoff_wins = integer(values.get("ВВбр", ""))
            lines.append(
                EuropeStatLine(
                    name,
                    source_id,
                    source.source_url,
                    source.provider,
                    source.league,
                    season,
                    regular_season,
                    marker,
                    games,
                    goals=values.get("Ш", ""),
                    assists=values.get("А", ""),
                    points=values.get("О", ""),
                    plus_minus=values.get("+/-", ""),
                    shots=values.get("БВ", ""),
                    blocks=values.get("БлБ", ""),
                    faceoff_wins=str(faceoff_wins) if values.get("ВВбр", "") else "",
                    faceoff_losses=(
                        str(max(faceoff_attempts - faceoff_wins, 0))
                        if values.get("Вбр", "") and values.get("ВВбр", "")
                        else ""
                    ),
                    faceoff_percentage=values.get("%Вбр", ""),
                )
            )
    return lines


def khl_profile_name(raw: str) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if not title_match:
        return ""
    title = re.sub(r"<[^>]+>", "", unescape(title_match.group(1)))
    russian_name = re.split(r",|\s+[–-]\s+", title, maxsplit=1)[0].strip()
    parts = russian_name.split()
    if len(parts) < 2 or not re.search(r"[А-Яа-яЁё]", russian_name):
        return ""
    return " ".join(parts[1:] + parts[:1])


def same_league_family(leagues: set[str], line: EuropeStatLine) -> bool:
    provider_family = {"swehockey": "sweden", "liiga": "finland", "khl": "russia"}[line.provider]
    return leagues_match_family(leagues, provider_family)


def leagues_match_family(leagues: set[str], family: str) -> bool:
    return bool(leagues & LEAGUE_FAMILIES[family]) or any(
        COUNTRY_LEAGUE_FAMILIES.get(league) == family for league in leagues
    )


def stat_key(row: dict[str, str]) -> tuple[str, str, str, bool] | None:
    if row.get("timing") != "pre_draft":
        return None
    return (
        row.get("player_id", ""),
        row.get("season", ""),
        normalize_league_name(row.get("league", "")),
        row.get("regular_season", "true").casefold() == "true",
    )


def build_stat_line(player_id: str, line: EuropeStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": line.league,
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": "",
        "timing": "pre_draft",
        "regular_season": str(line.regular_season).lower(),
        "goalie_minutes": line.goalie_minutes,
        "saves": line.saves,
        "goals_against": line.goals_against,
        "save_percentage": line.save_percentage,
        "goals_against_average": line.goals_against_average,
        "wins": line.wins,
        "losses": line.losses,
        "ties": line.ties,
        "shutouts": line.shutouts,
        "source": line.provider,
        "source_id": line.source_id,
        "source_url": line.source_url,
    }


def build_advanced_line(player_id: str, line: EuropeStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": line.league,
        "team": line.team,
        "timing": "pre_draft",
        "regular_season": str(line.regular_season).lower(),
        "games": line.games,
        "plus_minus": line.plus_minus,
        "shots": line.shots,
        "blocks": line.blocks,
        "faceoff_wins": line.faceoff_wins,
        "faceoff_losses": line.faceoff_losses,
        "faceoff_percentage": line.faceoff_percentage,
        "source": line.provider,
        "source_id": line.source_id,
        "source_url": line.source_url,
    }


def has_advanced_stats(line: EuropeStatLine) -> bool:
    return any(
        (
            line.plus_minus,
            line.shots,
            line.blocks,
            line.faceoff_wins,
            line.faceoff_losses,
            line.faceoff_percentage,
        )
    )


def build_match_row(
    player: dict[str, str],
    line: EuropeStatLine | None,
    matched: bool,
    match_method: str,
) -> dict[str, str]:
    return {
        "player_id": player["player_id"],
        "name": player["name"],
        "matched": str(matched).lower(),
        "match_method": match_method,
        "provider": line.provider if line else "",
        "league": line.league if line else "",
        "source_name": line.name if line else "",
        "source_id": line.source_id if line else "",
        "source_url": line.source_url if line else "",
        "team": line.team if line else "",
        "games": line.games if line else "",
        "points": line.points if line else "",
        "save_percentage": line.save_percentage if line else "",
    }


def person_identity_keys(name: str) -> set[str]:
    exact = normalize_person_key(name)
    transliterated = name.casefold().translate(CYRILLIC_TRANSLITERATION)
    parts = transliterated.split()
    if parts:
        parts[0] = RUSSIAN_FIRST_NAME_EQUIVALENTS.get(parts[0], parts[0])
        parts = [part[:-2] + "y" if part.endswith("iy") else part for part in parts]
    normalized_transliteration = normalize_person_key(" ".join(parts))
    return {key for key in (exact, normalized_transliteration) if key}


def deduplicate_source_lines(lines) -> list[EuropeStatLine]:
    unique: dict[tuple[str, ...], EuropeStatLine] = {}
    for line in lines:
        key_parts = (
            line.source_id,
            line.season,
            line.league,
            str(line.regular_season),
            line.team,
        )
        key = (*key_parts, line.source_url) if line.provider == "swehockey" else key_parts
        previous = unique.get(key)
        if previous is None or stat_line_detail_score(line) > stat_line_detail_score(previous):
            unique[key] = line
    aggregated: dict[tuple[str, str, str, bool, str], EuropeStatLine] = {}
    output: list[EuropeStatLine] = []
    for line in unique.values():
        if line.provider != "swehockey":
            output.append(line)
            continue
        key = (
            normalize_person_key(line.name),
            line.season,
            line.league,
            line.regular_season,
            line.team,
        )
        previous = aggregated.get(key)
        aggregated[key] = line if previous is None else combine_stat_lines(previous, line)
    return output + list(aggregated.values())


def stat_line_detail_score(line: EuropeStatLine) -> int:
    goalie_fields = (
        line.goalie_minutes,
        line.saves,
        line.goals_against,
        line.save_percentage,
        line.goals_against_average,
        line.wins,
        line.losses,
        line.shutouts,
    )
    skater_fields = (
        line.goals,
        line.assists,
        line.points,
        line.plus_minus,
        line.shots,
        line.faceoff_wins,
        line.faceoff_losses,
    )
    return sum(bool(value) for value in goalie_fields) * 2 + sum(
        bool(value) for value in skater_fields
    )


def combine_stat_lines(left: EuropeStatLine, right: EuropeStatLine) -> EuropeStatLine:
    games = integer(left.games) + integer(right.games)
    goalie_minutes = minutes_value(left.goalie_minutes) + minutes_value(right.goalie_minutes)
    saves = integer(left.saves) + integer(right.saves)
    goals_against = integer(left.goals_against) + integer(right.goals_against)
    faceoff_wins = integer(left.faceoff_wins) + integer(right.faceoff_wins)
    faceoff_losses = integer(left.faceoff_losses) + integer(right.faceoff_losses)
    return EuropeStatLine(
        name=left.name,
        source_id=combined_source_id(left, right),
        source_url=left.source_url,
        provider=left.provider,
        league=left.league,
        season=left.season,
        regular_season=left.regular_season,
        team=left.team,
        games=str(games),
        goals=sum_integer_text(left.goals, right.goals),
        assists=sum_integer_text(left.assists, right.assists),
        points=sum_integer_text(left.points, right.points),
        goalie_minutes=decimal_text(goalie_minutes),
        saves=str(saves) if left.saves or right.saves else "",
        goals_against=str(goals_against) if left.goals_against or right.goals_against else "",
        save_percentage=(
            f"{saves / (saves + goals_against):.3f}" if saves + goals_against else ""
        ),
        goals_against_average=(
            f"{goals_against * 60 / goalie_minutes:.2f}" if goalie_minutes else ""
        ),
        wins=sum_integer_text(left.wins, right.wins),
        losses=sum_integer_text(left.losses, right.losses),
        ties=sum_integer_text(left.ties, right.ties),
        shutouts=sum_integer_text(left.shutouts, right.shutouts),
        plus_minus=sum_integer_text(left.plus_minus, right.plus_minus),
        shots=sum_integer_text(left.shots, right.shots),
        blocks=sum_integer_text(left.blocks, right.blocks),
        faceoff_wins=str(faceoff_wins) if left.faceoff_wins or right.faceoff_wins else "",
        faceoff_losses=(
            str(faceoff_losses) if left.faceoff_losses or right.faceoff_losses else ""
        ),
        faceoff_percentage=(
            f"{faceoff_wins * 100 / (faceoff_wins + faceoff_losses):.1f}"
            if faceoff_wins + faceoff_losses
            else ""
        ),
    )


def combined_source_id(left: EuropeStatLine, right: EuropeStatLine) -> str:
    base_id, _, existing_feeds = left.source_id.partition("@")
    feed_ids = existing_feeds.split("+") if existing_feeds else []
    for url in (left.source_url, right.source_url):
        match = re.search(r"/(\d+)(?:[/?#]|$)", url)
        if match and match.group(1) not in feed_ids:
            feed_ids.append(match.group(1))
    if not feed_ids:
        return base_id
    return f"{base_id}@{'+'.join(feed_ids)}"


def sum_integer_text(left: str, right: str) -> str:
    return str(integer(left) + integer(right)) if left or right else ""


def minutes_value(raw: object) -> float:
    text = str(raw).strip()
    if ":" in text:
        minutes, _, seconds = text.partition(":")
        try:
            return float(minutes) + float(seconds) / 60
        except ValueError:
            return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def decimal_text(value_number: float) -> str:
    if not value_number:
        return ""
    return str(int(value_number)) if value_number.is_integer() else f"{value_number:.2f}"


def seconds_to_minutes_text(raw: object) -> str:
    try:
        return decimal_text(float(str(raw)) / 60)
    except (TypeError, ValueError):
        return ""


def display_swedish_name(name: str) -> str:
    last, separator, first = name.partition(",")
    return f"{first.strip()} {last.strip()}" if separator else name.strip()


def percent_to_decimal(value_text: str) -> str:
    try:
        return f"{float(value_text) / 100:.3f}"
    except (TypeError, ValueError):
        return ""


def normalize_save_percentage(raw: object) -> str:
    try:
        value_number = float(raw)
    except (TypeError, ValueError):
        return ""
    if value_number > 1:
        value_number /= 100
    return f"{value_number:.3f}"


def value(row: dict[str, object], key: str) -> str:
    raw = row.get(key, "")
    return "" if raw is None else str(raw)


def source_contains_provider(source: str, provider: str) -> bool:
    return provider in {part.strip() for part in source.split(";") if part.strip()}


def integer(raw: object) -> int:
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return 0
