"""AHL HockeyTech feed importer for organizational roster depth."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from draft_room_intelligence.data.team_rosters import RosterPlayer, write_roster_csv


AHL_APP_KEY = "ccb91f29d6744675"
AHL_CLIENT_CODE = "ahl"
AHL_LEAGUE_ID = "4"
AHL_SITE_ID = "3"
AHL_FEED_URL = "https://lscluster.hockeytech.com/feed/index.php"
DEFAULT_AHL_SEASON_ID = "86"
DEFAULT_AHL_SEASON_LABEL = "2024-25 Regular Season"
DEFAULT_PRESEASON_REFERENCE_DATE = date(2025, 9, 15)


NHL_TEAM_NAMES = {
    "ANA": "Anaheim Ducks",
    "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres",
    "CAR": "Carolina Hurricanes",
    "CBJ": "Columbus Blue Jackets",
    "CGY": "Calgary Flames",
    "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche",
    "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings",
    "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens",
    "NJD": "New Jersey Devils",
    "NSH": "Nashville Predators",
    "NYI": "New York Islanders",
    "NYR": "New York Rangers",
    "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins",
    "SEA": "Seattle Kraken",
    "SJS": "San Jose Sharks",
    "STL": "St. Louis Blues",
    "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs",
    "UTA": "Utah Mammoth",
    "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights",
    "WPG": "Winnipeg Jets",
    "WSH": "Washington Capitals",
}


AHL_TEAM_TO_NHL = {
    "ABB": "VAN",
    "BAK": "EDM",
    "BEL": "OTT",
    "BRI": "NYI",
    "CGY": "CGY",
    "CLT": "FLA",
    "CHI": "CAR",
    "CLE": "CBJ",
    "CV": "SEA",
    "COL": "COL",
    "GR": "DET",
    "HFD": "NYR",
    "HSK": "VGK",
    "HER": "WSH",
    "IA": "MIN",
    "LAV": "MTL",
    "LV": "PHI",
    "MB": "WPG",
    "MIL": "NSH",
    "ONT": "LAK",
    "PRO": "BOS",
    "ROC": "BUF",
    "RFD": "CHI",
    "SD": "ANA",
    "SJ": "SJS",
    "SPR": "STL",
    "SYR": "TBL",
    "TEX": "DAL",
    "TOR": "TOR",
    "TUC": "UTA",
    "UTC": "NJD",
    "WBS": "PIT",
}


@dataclass(frozen=True)
class AhlImportSummary:
    output_csv: Path
    season_id: str
    season_label: str
    teams_loaded: int
    skaters_loaded: int
    goalies_loaded: int
    roster_detail_players: int
    normalized_players: int


@dataclass(frozen=True)
class AhlTeam:
    team_id: str
    code: str
    name: str
    nhl_team_id: str


def import_ahl_rosters(
    output_csv: str | Path,
    *,
    season_id: str = DEFAULT_AHL_SEASON_ID,
    season_label: str = DEFAULT_AHL_SEASON_LABEL,
    reference_date: date = DEFAULT_PRESEASON_REFERENCE_DATE,
    minimum_games: int = 1,
) -> AhlImportSummary:
    teams = fetch_ahl_teams(season_id)
    detail_rows = fetch_roster_detail_rows(teams, season_id)
    skaters = fetch_player_stats(season_id, position="skaters", sort="points")
    goalies = fetch_player_stats(season_id, position="goalies", sort="wins")
    players = normalize_ahl_players(
        skaters + goalies,
        teams=teams,
        detail_rows=detail_rows,
        season_id=season_id,
        season_label=season_label,
        reference_date=reference_date,
        minimum_games=minimum_games,
    )
    write_roster_csv(output_csv, players)
    return AhlImportSummary(
        output_csv=Path(output_csv),
        season_id=season_id,
        season_label=season_label,
        teams_loaded=len(teams),
        skaters_loaded=len(skaters),
        goalies_loaded=len(goalies),
        roster_detail_players=len(detail_rows),
        normalized_players=len(players),
    )


def fetch_ahl_teams(season_id: str) -> dict[str, AhlTeam]:
    data = fetch_jsonp(
        {
            "feed": "statviewfeed",
            "view": "teamsForSeason",
            "season": season_id,
            "includeAll": "false",
        }
    )
    teams = {}
    for row in data.get("teamsNoAll", data.get("teams", [])):
        code = clean_text(row.get("team_code", ""))
        if not code:
            continue
        nhl_team_id = AHL_TEAM_TO_NHL.get(code, "")
        if not nhl_team_id:
            continue
        teams[code] = AhlTeam(
            team_id=clean_text(row.get("id", "")),
            code=code,
            name=clean_text(row.get("name", code)),
            nhl_team_id=nhl_team_id,
        )
    return teams


def fetch_roster_detail_rows(teams: dict[str, AhlTeam], season_id: str) -> dict[tuple[str, str], dict[str, str]]:
    details: dict[tuple[str, str], dict[str, str]] = {}
    for team in teams.values():
        data = fetch_jsonp(
            {
                "feed": "statviewfeed",
                "view": "roster",
                "team_id": team.team_id,
                "season_id": season_id,
                "rosterstatus": "",
            }
        )
        for section_group in data.get("roster", []):
            for section in section_group.get("sections", []):
                for item in section.get("data", []):
                    row = item.get("row", {})
                    player_id = clean_text(row.get("player_id", ""))
                    if player_id:
                        details[(team.code, player_id)] = {str(key): clean_text(value) for key, value in row.items()}
    return details


def fetch_player_stats(season_id: str, *, position: str, sort: str) -> list[dict[str, str]]:
    params = {
        "feed": "statviewfeed",
        "view": "players",
        "season": season_id,
        "team": "all",
        "position": position,
        "rookies": "0",
        "statsType": "standard",
        "rosterstatus": "",
        "first": "0",
        "limit": "2000",
        "sort": sort,
        "order_direction": "normal",
        "division": "",
        "conference": "",
    }
    if position == "goalies":
        params["qualified"] = "0"
    data = fetch_jsonp(params)
    sections = data[0].get("sections", []) if data else []
    rows = sections[0].get("data", []) if sections else []
    return [{str(key): clean_text(value) for key, value in item.get("row", {}).items()} for item in rows]


def normalize_ahl_players(
    stats_rows: list[dict[str, str]],
    *,
    teams: dict[str, AhlTeam],
    detail_rows: dict[tuple[str, str], dict[str, str]],
    season_id: str,
    season_label: str,
    reference_date: date,
    minimum_games: int,
) -> list[RosterPlayer]:
    players: list[RosterPlayer] = []
    for row in stats_rows:
        if row.get("position", "").upper() == "G" and "save_percentage" not in row:
            continue
        games = to_int(row.get("games_played", ""))
        if games < minimum_games:
            continue
        player_id = row.get("player_id", "")
        ahl_code = row.get("team_code", "")
        team = teams.get(ahl_code)
        if team is None:
            continue
        detail = detail_rows.get((ahl_code, player_id), {})
        nhl_team_id = team.nhl_team_id
        players.append(
            RosterPlayer(
                team_id=nhl_team_id,
                team_name=NHL_TEAM_NAMES.get(nhl_team_id, nhl_team_id),
                league_level="AHL",
                affiliate_of=team.name,
                player_id=f"ahl-{player_id}",
                player_name=row.get("name", ""),
                position=normalize_position(row.get("position", detail.get("position", ""))),
                handedness=detail.get("shoots", "").upper(),
                age=age_on(detail.get("birthdate", ""), reference_date),
                height_cm=height_to_cm(detail.get("height_hyphenated", "")),
                weight_kg=pounds_to_kg(detail.get("w", "")),
                games=games,
                goals=to_int(row.get("goals", "")),
                assists=to_int(row.get("assists", "")),
                points=to_int(row.get("points", "")) or to_int(row.get("goals", "")) + to_int(row.get("assists", "")),
                plus_minus=to_optional_int(row.get("plus_minus", "")),
                goalie_minutes=minutes_to_float(row.get("minutes_played", "")),
                goalie_wins=to_int(row.get("wins", "")),
                goalie_saves=to_int(row.get("saves", "")),
                goalie_shots_against=to_int(row.get("shots", "")),
                goalie_goals_against=to_int(row.get("goals_against", "")),
                goalie_save_percentage=to_optional_float(row.get("save_percentage", "")),
                goalie_goals_against_average=to_optional_float(row.get("goals_against_average", "")),
                goalie_shutouts=to_int(row.get("shutouts", "")),
                source="ahl_hockeytech",
                source_id=f"{season_id}:{ahl_code}:{player_id}",
                source_url=player_stats_source_url(season_id),
            )
        )
    return sorted(players, key=lambda player: (player.team_id, player.affiliate_of, player.player_name))


def fetch_jsonp(params: dict[str, str]) -> object:
    request_params = {
        **params,
        "site_id": AHL_SITE_ID,
        "league_id": AHL_LEAGUE_ID,
        "lang": "en",
        "key": AHL_APP_KEY,
        "client_code": AHL_CLIENT_CODE,
        "callback": "JSON_CALLBACK",
    }
    url = f"{AHL_FEED_URL}?{urlencode(request_params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": player_stats_source_url(str(params.get("season", params.get("season_id", "")))),
        },
    )
    with urlopen(request, timeout=45) as response:
        text = response.read().decode("utf-8", "ignore")
    match = re.match(r"^[^(]+\((.*)\)\s*$", text, re.S)
    if not match:
        raise ValueError(f"AHL feed did not return JSONP: {url}")
    return json.loads(match.group(1))


def player_stats_source_url(season_id: str) -> str:
    return (
        "https://theahl.com/stats/player-stats/all-teams/"
        f"{season_id}?playertype=skater&position=skaters&rookie=no&sort=points&statstype=standard&page=1&league=4"
    )


def normalize_position(value: str) -> str:
    normalized = clean_text(value).upper()
    return "LW" if normalized == "F" else normalized


def height_to_cm(value: str) -> int:
    match = re.match(r"^\s*(\d+)-(\d+)\s*$", value)
    if not match:
        return 0
    feet = int(match.group(1))
    inches = int(match.group(2))
    return round(((feet * 12) + inches) * 2.54)


def pounds_to_kg(value: str) -> int:
    pounds = to_int(value)
    return round(pounds * 0.45359237) if pounds else 0


def age_on(birthdate: str, reference_date: date) -> float:
    if not birthdate:
        return 0.0
    try:
        born = datetime.strptime(birthdate, "%Y-%m-%d").date()
    except ValueError:
        return 0.0
    return round((reference_date - born).days / 365.25, 1)


def to_int(value: str) -> int:
    value = clean_text(value)
    return int(float(value)) if value else 0


def to_optional_int(value: str) -> int | None:
    value = clean_text(value)
    return int(float(value)) if value else None


def to_optional_float(value: str) -> float | None:
    value = clean_text(value)
    return float(value) if value else None


def minutes_to_float(value: str) -> float | None:
    value = clean_text(value)
    if not value:
        return None
    if ":" in value:
        minutes, seconds = value.split(":", maxsplit=1)
        return int(minutes) + int(seconds) / 60
    return float(value)


def clean_text(value: object) -> str:
    return str(value or "").strip()
