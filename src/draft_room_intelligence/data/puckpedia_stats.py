"""Enrich demo stat lines from public PuckPedia player pages."""

from __future__ import annotations

import csv
import re
import shutil
import time
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from draft_room_intelligence.data.chl_stats import normalize_person_key, read_table
from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name


PUCKPEDIA_MATCH_COLUMNS = [
    "player_id",
    "name",
    "matched",
    "slug",
    "league",
    "team",
    "games",
    "goals",
    "assists",
    "points",
    "regular_season",
    "source_url",
]


KNOWN_LEAGUES = sorted(
    {
        "AHL",
        "BCHL",
        "CCHL",
        "DEL",
        "H-East",
        "KHL",
        "Liiga",
        "MHL",
        "NCAA",
        "NCHC",
        "NTDP",
        "OHL",
        "QMJHL",
        "SHL",
        "USHL",
        "USHS-MN",
        "USNTDP",
        "WHL",
        "WJAC-19",
        "WJC-18",
        "WHC-17",
    },
    key=len,
    reverse=True,
)


@dataclass(frozen=True)
class PuckPediaStatLine:
    name: str
    slug: str
    source_url: str
    season: str
    league: str
    team: str
    games: str
    goals: str
    assists: str
    points: str
    regular_season: bool


@dataclass(frozen=True)
class PuckPediaStatsSummary:
    players_scanned: int
    pages_fetched: int
    source_rows: int
    matched_players: int
    output_stat_lines: int
    match_report_path: Path


def enrich_puckpedia_stats(
    base_dir: str | Path,
    output_dir: str | Path,
    *,
    season: str,
    cache_dir: str | Path | None = None,
    request_delay_seconds: float = 0.2,
    limit: int | None = None,
) -> PuckPediaStatsSummary:
    source_root = Path(base_dir)
    target_root = Path(output_dir)
    if not source_root.exists():
        raise ValueError(f"missing base dataset directory: {source_root}")

    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    players = read_table(source_root / "players.csv")
    selected_players = players[:limit] if limit is not None else players
    base_stat_lines = read_table(source_root / "season_stat_lines.csv")
    source_by_player_id: dict[str, list[PuckPediaStatLine]] = {}
    report_rows: list[dict[str, str]] = []
    pages_fetched = 0

    for index, player in enumerate(selected_players):
        if index and request_delay_seconds > 0:
            time.sleep(request_delay_seconds)
        slug = slugify_player_name(player["name"])
        source_url = f"https://puckpedia.com/player/{slug}"
        try:
            html = fetch_cached_player_page(slug, source_url, cache_dir=cache_dir)
        except (HTTPError, URLError, TimeoutError):
            html = ""
        if not html:
            report_rows.append(build_match_row(player, None, slug=slug))
            continue
        pages_fetched += 1
        lines = parse_puckpedia_stat_lines(html, player["name"], slug, source_url, season=season)
        if not lines:
            report_rows.append(build_match_row(player, None, slug=slug))
            continue
        source_by_player_id[player["player_id"]] = lines
        for line in lines:
            report_rows.append(build_match_row(player, line, slug=slug))

    output_stat_lines: list[dict[str, str]] = []
    covered_keys: set[tuple[str, str, str, bool]] = set()
    for row in base_stat_lines:
        row_key = stat_row_key(row)
        if row_key is not None:
            covered_keys.add(row_key)
        if should_drop_placeholder(row, source_by_player_id.get(row.get("player_id", ""), [])):
            continue
        output_stat_lines.append(row)

    for player_id, lines in sorted(source_by_player_id.items()):
        for line in lines:
            key = source_line_key(player_id, line)
            if key in covered_keys:
                continue
            covered_keys.add(key)
            output_stat_lines.append(build_normalized_stat_line(player_id, line))

    write_table(target_root / "players.csv", PLAYER_COLUMNS, players)
    write_table(target_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, output_stat_lines)
    write_table(target_root / "puckpedia_stat_matches.csv", PUCKPEDIA_MATCH_COLUMNS, report_rows)

    return PuckPediaStatsSummary(
        players_scanned=len(selected_players),
        pages_fetched=pages_fetched,
        source_rows=sum(len(lines) for lines in source_by_player_id.values()),
        matched_players=len(source_by_player_id),
        output_stat_lines=len(output_stat_lines),
        match_report_path=target_root / "puckpedia_stat_matches.csv",
    )


def parse_puckpedia_stat_lines(
    html: str,
    name: str,
    slug: str,
    source_url: str,
    *,
    season: str,
) -> list[PuckPediaStatLine]:
    lines: list[PuckPediaStatLine] = []
    for text in extract_text_lines(html):
        if not text.startswith(f"{season} "):
            continue
        regular, playoffs = parse_stat_text_line(text, season=season)
        if regular is not None:
            lines.append(
                PuckPediaStatLine(
                    name=name,
                    slug=slug,
                    source_url=source_url,
                    regular_season=True,
                    **regular,
                )
            )
        if playoffs is not None:
            lines.append(
                PuckPediaStatLine(
                    name=name,
                    slug=slug,
                    source_url=source_url,
                    regular_season=False,
                    **playoffs,
                )
            )
    return deduplicate_source_lines(lines)


def parse_stat_text_line(text: str, *, season: str) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    pattern = re.compile(
        rf"^{re.escape(season)}\s+\d+\s+(?P<body>.+?)\s+"
        r"(?P<gp>\d+)\s+(?P<g>\d+)\s+(?P<a>\d+)\s+(?P<pts>\d+)\s+(?P<pim>\d+)"
        r"(?:\s+Playoffs\s+(?P<pgp>\d+)\s+(?P<pg>\d+)\s+(?P<pa>\d+)\s+(?P<ppts>\d+)\s+(?P<ppim>\d+))?$"
    )
    match = pattern.match(text)
    if not match:
        return None, None
    league, team = split_league_team(match.group("body"))
    if not league or not team:
        return None, None
    regular = {
        "season": season,
        "league": normalize_league_name(league),
        "team": team,
        "games": match.group("gp"),
        "goals": match.group("g"),
        "assists": match.group("a"),
        "points": match.group("pts"),
    }
    playoffs = None
    if match.group("pgp"):
        playoffs = {
            "season": season,
            "league": normalize_league_name(league),
            "team": team,
            "games": match.group("pgp"),
            "goals": match.group("pg"),
            "assists": match.group("pa"),
            "points": match.group("ppts"),
        }
    return regular, playoffs


def split_league_team(body: str) -> tuple[str, str]:
    for league in KNOWN_LEAGUES:
        prefix = f"{league} "
        if body == league:
            return league, ""
        if body.startswith(prefix):
            return league, body[len(prefix) :].strip()
    parts = body.split(" ", 1)
    if len(parts) != 2:
        return "", ""
    return parts[0], parts[1].strip()


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.lines.append(text)


def extract_text_lines(html: str) -> list[str]:
    parser = TextExtractor()
    parser.feed(html)
    return parser.lines


def deduplicate_source_lines(lines: list[PuckPediaStatLine]) -> list[PuckPediaStatLine]:
    seen: set[tuple[str, str, str, bool]] = set()
    deduped: list[PuckPediaStatLine] = []
    for line in lines:
        key = (line.season, normalize_league_name(line.league), normalize_person_key(line.team), line.regular_season)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def should_drop_placeholder(row: dict[str, str], source_lines: list[PuckPediaStatLine]) -> bool:
    if row.get("timing") != "pre_draft" or row.get("source") != "wikipedia":
        return False
    row_league = normalize_league_name(row.get("league", ""))
    return any(normalize_league_name(line.league) == row_league for line in source_lines)


def stat_row_key(row: dict[str, str]) -> tuple[str, str, str, bool] | None:
    if row.get("timing") != "pre_draft":
        return None
    if row.get("source") == "wikipedia" and not row.get("games"):
        return None
    return (
        row.get("player_id", ""),
        row.get("season", ""),
        normalize_league_name(row.get("league", "")),
        row.get("regular_season", "true").lower() != "false",
    )


def source_line_key(player_id: str, line: PuckPediaStatLine) -> tuple[str, str, str, bool]:
    return (player_id, line.season, normalize_league_name(line.league), line.regular_season)


def build_normalized_stat_line(player_id: str, line: PuckPediaStatLine) -> dict[str, str]:
    return {
        "player_id": player_id,
        "season": line.season,
        "league": normalize_league_name(line.league),
        "team": line.team,
        "games": line.games,
        "goals": line.goals,
        "assists": line.assists,
        "points": line.points,
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true" if line.regular_season else "false",
        "source": "puckpedia",
        "source_id": line.slug,
        "source_url": line.source_url,
    }


def build_match_row(
    player: dict[str, str],
    line: PuckPediaStatLine | None,
    *,
    slug: str,
) -> dict[str, str]:
    return {
        "player_id": player.get("player_id", ""),
        "name": player.get("name", ""),
        "matched": "true" if line is not None else "false",
        "slug": slug,
        "league": line.league if line is not None else "",
        "team": line.team if line is not None else "",
        "games": line.games if line is not None else "",
        "goals": line.goals if line is not None else "",
        "assists": line.assists if line is not None else "",
        "points": line.points if line is not None else "",
        "regular_season": "true" if line is not None and line.regular_season else "false",
        "source_url": line.source_url if line is not None else f"https://puckpedia.com/player/{slug}",
    }


def fetch_cached_player_page(slug: str, source_url: str, *, cache_dir: str | Path | None) -> str:
    if cache_dir is None:
        return fetch_puckpedia_text(source_url)
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = cache_root / f"{slug}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    html = fetch_puckpedia_text(source_url)
    cache_path.write_text(html, encoding="utf-8")
    return html


def fetch_puckpedia_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def slugify_player_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower().replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
