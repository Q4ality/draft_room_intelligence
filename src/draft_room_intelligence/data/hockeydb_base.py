"""Build a normalized draft-year base dataset from local HockeyDB HTML pages."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from draft_room_intelligence.data.eliteprospects_csv import ADVANCED_STAT_LINE_COLUMNS
from draft_room_intelligence.data.league_standardization import normalize_league_name

TEAM_IDS = {
    "Anaheim": "ANA",
    "Arizona": "ARI",
    "Boston": "BOS",
    "Buffalo": "BUF",
    "Calgary": "CGY",
    "Carolina": "CAR",
    "Chicago": "CHI",
    "Colorado": "COL",
    "Columbus": "CBJ",
    "Dallas": "DAL",
    "Detroit": "DET",
    "Edmonton": "EDM",
    "Florida": "FLA",
    "Los Angeles": "LAK",
    "Minnesota": "MIN",
    "Montreal": "MTL",
    "Nashville": "NSH",
    "New Jersey": "NJD",
    "NY Islanders": "NYI",
    "NY Rangers": "NYR",
    "Ottawa": "OTT",
    "Philadelphia": "PHI",
    "Pittsburgh": "PIT",
    "San Jose": "SJS",
    "St. Louis": "STL",
    "Tampa Bay": "TBL",
    "Toronto": "TOR",
    "Vancouver": "VAN",
    "Vegas": "VGK",
    "Washington": "WSH",
    "Winnipeg": "WPG",
}

@dataclass(frozen=True)
class HockeyDbBaseETLConfig:
    draft_year: int
    draft_html_path: Path
    output_dir: Path
    source_url: str = "https://www.hockeydb.com/"
    player_pages_dir: Path | None = None


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.in_cell:
            self.current_row.append(clean("".join(self.current_cell)))
            self.in_cell = False
        elif tag == "tr" and self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


class StatsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.current_cell: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"td", "th"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.in_cell:
            self.current_row.append(clean("".join(self.current_cell)))
            self.in_cell = False
        elif tag == "tr" and self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def generate_hockeydb_base_tables(config: HockeyDbBaseETLConfig) -> Path:
    html = config.draft_html_path.read_text(encoding="utf-8")
    picks = parse_rows(html, config.draft_year)
    if not picks:
        raise ValueError(f"no draft picks found in {config.draft_html_path}")
    enriched = [
        enrich_pick(pick, config.player_pages_dir, config.draft_year)
        for pick in picks
    ]

    source_fields = {
        "source": "hockeydb",
        "source_url": config.source_url,
    }
    root = config.output_dir
    root.mkdir(parents=True, exist_ok=True)

    write_csv(
        root / "players.csv",
        [
            "player_id",
            "name",
            "birth_date",
            "nationality",
            "position",
            "handedness",
            "height_cm",
            "weight_kg",
            "age_at_draft",
            "source",
            "source_id",
            "source_url",
        ],
        [
            {
                **source_fields,
                "player_id": item["pick"]["player_id"],
                "source_id": item["pick"]["player_id"],
                "name": item["pick"]["name"],
                "position": item["pick"]["position"],
                "birth_date": item["birth_date"],
                "handedness": item["handedness"],
                "height_cm": item["height_cm"],
                "weight_kg": item["weight_kg"],
                "age_at_draft": item["age_at_draft"],
            }
            for item in enriched
        ],
    )
    write_csv(
        root / "draft_selections.csv",
        [
            "player_id",
            "draft_year",
            "team_id",
            "team_name",
            "round_number",
            "overall_pick",
            "drafted_from_team",
            "drafted_from_league",
            "source",
            "source_id",
            "source_url",
        ],
        [
            {
                **source_fields,
                "player_id": item["pick"]["player_id"],
                "source_id": item["pick"]["player_id"],
                "draft_year": str(config.draft_year),
                "team_id": item["pick"]["team_id"],
                "team_name": item["pick"]["team_name"],
                "round_number": item["pick"]["round_number"],
                "overall_pick": item["pick"]["overall_pick"],
                "drafted_from_team": item["pick"]["drafted_from_team"],
                "drafted_from_league": item["pick"]["drafted_from_league"],
            }
            for item in enriched
        ],
    )
    season = season_label(config.draft_year)
    write_csv(
        root / "season_stat_lines.csv",
        [
            "player_id",
            "season",
            "league",
            "team",
            "games",
            "goals",
            "assists",
            "points",
            "age",
            "timing",
            "regular_season",
            "source",
            "source_id",
            "source_url",
        ],
        build_pre_draft_stat_rows(enriched, source_fields, season),
    )
    write_csv(root / "advanced_stat_lines.csv", ADVANCED_STAT_LINE_COLUMNS, [])
    write_csv(
        root / "nhl_outcomes.csv",
        [
            "player_id",
            "nhl_games",
            "nhl_goals",
            "nhl_assists",
            "nhl_points",
            "seasons_played",
            "last_season",
            "value_proxy",
            "source",
            "source_id",
            "source_url",
        ],
        [
            {
                **source_fields,
                "player_id": item["pick"]["player_id"],
                "source_id": item["pick"]["player_id"],
                "nhl_games": item["pick"]["nhl_games"] or "0",
                "nhl_goals": item["pick"]["nhl_goals"] or "0",
                "nhl_assists": item["pick"]["nhl_assists"] or "0",
                "nhl_points": item["pick"]["nhl_points"] or "0",
                "last_season": item["pick"]["last_season"],
            }
            for item in enriched
        ],
    )
    write_csv(
        root / "rankings.csv",
        [
            "player_id",
            "draft_year",
            "source",
            "rank",
            "scope",
            "position",
            "source_id",
            "source_url",
        ],
        [
            {
                "player_id": item["pick"]["player_id"],
                "draft_year": str(config.draft_year),
                "source": "draft_slot_proxy",
                "rank": item["pick"]["overall_pick"],
                "scope": "all_drafted_players",
                "position": item["pick"]["position"],
                "source_id": item["pick"]["player_id"],
                "source_url": config.source_url,
            }
            for item in enriched
        ],
    )
    return root


def enrich_pick(
    pick: dict[str, str],
    player_pages_dir: Path | None,
    draft_year: int,
) -> dict[str, object]:
    details = {
        "birth_date": "",
        "handedness": "",
        "height_cm": "",
        "weight_kg": "",
        "age_at_draft": "",
    }
    pre_draft_rows: list[dict[str, object]] = []
    if player_pages_dir is not None:
        page_path = player_pages_dir / f"{pick['player_id']}.html"
        if page_path.exists():
            html = page_path.read_text(encoding="utf-8")
            parsed = parse_player_page(html, draft_year)
            details = {
                "birth_date": parsed["birth_date"],
                "handedness": parsed["handedness"],
                "height_cm": parsed["height_cm"],
                "weight_kg": parsed["weight_kg"],
                "age_at_draft": parsed["age_at_draft"],
            }
            pre_draft_rows = choose_pre_draft_rows(pick, parsed["stats_rows"], draft_year)
    return {"pick": pick, **details, "pre_draft_rows": pre_draft_rows}


def parse_player_page(html: str, draft_year: int) -> dict[str, object]:
    birth_date = parse_birth_date(html)
    height_cm, weight_kg = parse_metric_measurements(html)
    return {
        "birth_date": birth_date.isoformat() if birth_date else "",
        "height_cm": int_text(height_cm),
        "weight_kg": int_text(weight_kg),
        "age_at_draft": f"{age_at_draft(birth_date, draft_year):.2f}" if birth_date else "",
        "handedness": parse_handedness(html),
        "stats_rows": parse_stats_rows(html),
    }


def parse_birth_date(html: str) -> date | None:
    match = re.search(r"Born ([A-Z][a-z]+ \d{1,2} \d{4})", html)
    if not match:
        return None
    value = match.group(1)
    for date_format in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass
    return None


def parse_metric_measurements(html: str) -> tuple[int | None, int | None]:
    match = re.search(r"\[(\d+) cm/(\d+) kg\]", html)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_handedness(html: str) -> str:
    match = re.search(r"-- shoots ([LRC])<br", html)
    if match:
        return match.group(1)
    match = re.search(r"-- catches ([LRC])<br", html)
    if match:
        return match.group(1)
    return ""


def parse_stats_rows(html: str) -> list[dict[str, object]]:
    parser = StatsParser()
    parser.feed(html)
    rows: list[dict[str, object]] = []
    for row in parser.rows:
        if len(row) < 7 or not re.match(r"^\d{4}-\d{2}$", row[0]):
            continue
        games = parse_int(row[3])
        if games is None:
            continue
        rows.append(
            {
                "season": row[0],
                "team": row[1],
                "league": normalize_league_name(row[2]),
                "games": games,
                "goals": parse_int(row[4]),
                "assists": parse_int(row[5]),
                "points": parse_int(row[6]),
            }
        )
    return rows


def choose_pre_draft_rows(
    pick: dict[str, str],
    stats_rows: list[dict[str, object]],
    draft_year: int,
) -> list[dict[str, object]]:
    target_season = season_label(draft_year)
    season_rows = [row for row in stats_rows if row["season"] == target_season]
    if not season_rows:
        return []
    league_matches = [row for row in season_rows if row["league"] == pick["drafted_from_league"]]
    if league_matches:
        return sorted(league_matches, key=lambda row: int(row["games"] or 0), reverse=True)
    team_matches = [
        row for row in season_rows if normalize_name(str(row["team"])) == normalize_name(pick["drafted_from_team"])
    ]
    if team_matches:
        return sorted(team_matches, key=lambda row: int(row["games"] or 0), reverse=True)
    return sorted(season_rows, key=lambda row: int(row["games"] or 0), reverse=True)


def build_pre_draft_stat_rows(
    enriched: list[dict[str, object]],
    source_fields: dict[str, str],
    default_season: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in enriched:
        pick = item["pick"]
        pre_draft_rows = item.get("pre_draft_rows") or []
        if not pre_draft_rows:
            pre_draft_rows = [
                {
                    "season": default_season,
                    "league": pick["drafted_from_league"],
                    "team": pick["drafted_from_team"],
                    "games": None,
                    "goals": None,
                    "assists": None,
                    "points": None,
                }
            ]
        for stat_row in pre_draft_rows:
            rows.append(
                {
                    **source_fields,
                    "player_id": pick["player_id"],
                    "source_id": pick["player_id"],
                    "season": str(stat_row.get("season", default_season)),
                    "league": str(stat_row.get("league", pick["drafted_from_league"])),
                    "team": str(stat_row.get("team", pick["drafted_from_team"])),
                    "games": int_text(stat_row.get("games")),
                    "goals": int_text(stat_row.get("goals")),
                    "assists": int_text(stat_row.get("assists")),
                    "points": int_text(stat_row.get("points")),
                    "timing": "pre_draft",
                    "regular_season": "true",
                }
            )
    return rows


def parse_rows(html: str, draft_year: int) -> list[dict[str, str]]:
    parser = TableParser()
    parser.feed(html)
    picks: list[dict[str, str]] = []
    for row in parser.rows:
        if len(row) < 6:
            continue
        if not row[0].isdigit() or not row[1].isdigit():
            continue
        drafted_from_team, drafted_from_league = split_team_league(row[5])
        player = row[3]
        pick = row[1]
        picks.append(
            {
                "player_id": f"{draft_year}-{int(pick):03d}-{slugify(player)}",
                "round_number": row[0],
                "overall_pick": pick,
                "team_name": row[2],
                "team_id": TEAM_IDS.get(row[2], row[2].upper().replace(" ", "")),
                "name": player,
                "position": normalize_position(row[4]),
                "drafted_from_team": drafted_from_team,
                "drafted_from_league": drafted_from_league,
                "nhl_games": int_or_blank(row[6]) if len(row) > 6 else "",
                "nhl_goals": int_or_blank(row[7]) if len(row) > 7 else "",
                "nhl_assists": int_or_blank(row[8]) if len(row) > 8 else "",
                "nhl_points": int_or_blank(row[9]) if len(row) > 9 else "",
                "last_season": row[11] if len(row) > 11 else "",
            }
        )
    return picks


def split_team_league(value: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)(?: \[(.*?)\]| \((.*?)\))?$", value)
    if not match:
        return value, "Unknown"
    team = clean(match.group(1))
    league = clean(match.group(2) or match.group(3) or "Unknown")
    return team, normalize_league_name(league)


def season_label(draft_year: int) -> str:
    return f"{draft_year - 1}-{str(draft_year)[-2:]}"


def age_at_draft(birth_date: date, draft_year: int) -> float:
    draft_date = date(draft_year, 6, 21)
    return round((draft_date - birth_date).days / 365.25, 2)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_position(pos: str) -> str:
    return {"L": "LW", "R": "RW", "F": "F"}.get(pos, pos)


def int_or_blank(value: str) -> str:
    return value if value.isdigit() else ""


def int_text(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)


def parse_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value.isdigit() else None


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
