"""Import NHL roster and club-stat payloads into normalized team roster rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from draft_room_intelligence.data.team_rosters import RosterPlayer, write_roster_csv


NHL_API_BASE_URL = "https://api-web.nhle.com/v1"

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


@dataclass(frozen=True)
class NhlRosterImportSummary:
    output_csv: Path
    teams_requested: int
    teams_loaded: int
    roster_players: int
    stats_teams_loaded: int


def import_nhl_rosters(
    output_csv: str | Path,
    *,
    team_codes: list[str] | None = None,
    season: str = "",
    game_type: int = 2,
    roster_json_dir: str | Path | None = None,
    stats_json_dir: str | Path | None = None,
    as_of: date | None = None,
) -> NhlRosterImportSummary:
    """Load NHL roster rows from cached JSON or the public NHL API."""

    teams = normalize_team_codes(team_codes or list(NHL_TEAM_NAMES))
    players: list[RosterPlayer] = []
    teams_loaded = 0
    stats_loaded = 0
    for team_code in teams:
        roster_payload = load_roster_payload(team_code, roster_json_dir=roster_json_dir)
        stats_payload = load_stats_payload(
            team_code,
            season=season,
            game_type=game_type,
            stats_json_dir=stats_json_dir,
        )
        if stats_payload:
            stats_loaded += 1
        team_players = parse_nhl_roster_payload(
            team_code,
            roster_payload,
            stats_payload=stats_payload,
            as_of=as_of,
        )
        if team_players:
            teams_loaded += 1
        players.extend(team_players)

    output_path = Path(output_csv)
    write_roster_csv(output_path, players)
    return NhlRosterImportSummary(
        output_csv=output_path,
        teams_requested=len(teams),
        teams_loaded=teams_loaded,
        roster_players=len(players),
        stats_teams_loaded=stats_loaded,
    )


def parse_nhl_roster_payload(
    team_code: str,
    roster_payload: dict,
    *,
    stats_payload: dict | None = None,
    as_of: date | None = None,
) -> list[RosterPlayer]:
    team_id = team_code.upper()
    team_name = team_name_from_payload(team_id, roster_payload)
    stats_by_player_id = build_stats_by_player_id(stats_payload or {})
    players: list[RosterPlayer] = []
    for group in ("forwards", "defensemen", "goalies"):
        for raw_player in roster_payload.get(group, []):
            player_id = str(first_value(raw_player, "id", "playerId") or "")
            if not player_id:
                continue
            stats = stats_by_player_id.get(player_id, {})
            position = str(first_value(raw_player, "positionCode", "position") or "")
            if not position:
                position = str(first_value(stats, "positionCode", "position") or "")
            games = int_value(first_value(stats, "gamesPlayed", "games", "gp"))
            goals = int_value(first_value(stats, "goals", "g"))
            assists = int_value(first_value(stats, "assists", "a"))
            points = int_value(first_value(stats, "points", "p"))
            players.append(
                RosterPlayer(
                    team_id=team_id,
                    team_name=team_name,
                    league_level="NHL",
                    affiliate_of="",
                    player_id=f"nhl-{player_id}",
                    player_name=player_name(raw_player, stats),
                    position=position,
                    handedness=str(first_value(raw_player, "shootsCatches", "shoots") or "").upper(),
                    age=age_from_birth_date(str(first_value(raw_player, "birthDate") or ""), as_of=as_of),
                    height_cm=inches_to_cm(int_value(first_value(raw_player, "heightInInches"))),
                    weight_kg=pounds_to_kg(int_value(first_value(raw_player, "weightInPounds"))),
                    games=games,
                    goals=goals,
                    assists=assists,
                    points=points,
                    plus_minus=optional_int_value(first_value(stats, "plusMinus", "plusminus")),
                    time_on_ice_per_game=time_on_ice_minutes(
                        first_value(
                            stats,
                            "timeOnIcePerGame",
                            "avgTimeOnIcePerGame",
                            "avgTimeOnIce",
                            "toiPerGame",
                        )
                    ),
                    source="nhl_api",
                    source_id=player_id,
                    source_url=f"{NHL_API_BASE_URL}/player/{player_id}/landing",
                )
            )
    return players


def load_roster_payload(team_code: str, *, roster_json_dir: str | Path | None) -> dict:
    if roster_json_dir is not None:
        return read_json_payload(Path(roster_json_dir) / f"{team_code.upper()}.roster.json")
    return fetch_json(f"{NHL_API_BASE_URL}/roster/{team_code.upper()}/current")


def load_stats_payload(
    team_code: str,
    *,
    season: str,
    game_type: int,
    stats_json_dir: str | Path | None,
) -> dict:
    if stats_json_dir is not None:
        path = Path(stats_json_dir) / f"{team_code.upper()}.stats.json"
        return read_json_payload(path) if path.exists() else {}
    if not season:
        return {}
    return fetch_json(f"{NHL_API_BASE_URL}/club-stats/{team_code.upper()}/{season}/{game_type}")


def build_stats_by_player_id(payload: dict) -> dict[str, dict]:
    stats_by_id: dict[str, dict] = {}
    for collection_key in ("skaters", "forwards", "defensemen", "goalies"):
        for row in payload.get(collection_key, []) or []:
            player_id = first_value(row, "playerId", "id")
            if player_id is not None:
                stats_by_id[str(player_id)] = row
    return stats_by_id


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "draft-room-intelligence/0.1"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_json_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_team_codes(team_codes: list[str]) -> list[str]:
    return [team_code.strip().upper() for team_code in team_codes if team_code.strip()]


def team_name_from_payload(team_code: str, payload: dict) -> str:
    for key in ("teamName", "name"):
        value = localized_text(payload.get(key))
        if value:
            return value
    return NHL_TEAM_NAMES.get(team_code, team_code)


def player_name(roster_row: dict, stats_row: dict) -> str:
    full_name = localized_text(first_value(roster_row, "fullName", "name")) or str(
        first_value(stats_row, "skaterFullName", "goalieFullName", "name") or ""
    )
    if full_name:
        return full_name
    first_name = localized_text(roster_row.get("firstName"))
    last_name = localized_text(roster_row.get("lastName"))
    return " ".join(part for part in (first_name, last_name) if part)


def localized_text(value) -> str:
    if isinstance(value, dict):
        return str(value.get("default") or value.get("en") or "").strip()
    return str(value or "").strip()


def first_value(row: dict, *keys: str):
    for key in keys:
        if key in row and row[key] not in ("", None):
            return row[key]
    return None


def age_from_birth_date(value: str, *, as_of: date | None = None) -> float:
    if not value:
        return 0.0
    try:
        birth_date = datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0.0
    reference_date = as_of or date.today()
    return round((reference_date - birth_date).days / 365.25, 1)


def int_value(value) -> int:
    if value in ("", None):
        return 0
    return int(float(value))


def optional_int_value(value) -> int | None:
    if value in ("", None):
        return None
    return int(float(value))


def inches_to_cm(inches: int) -> int:
    return round(inches * 2.54) if inches else 0


def pounds_to_kg(pounds: int) -> int:
    return round(pounds * 0.453592) if pounds else 0


def time_on_ice_minutes(value) -> float | None:
    if value in ("", None):
        return None
    if isinstance(value, str) and ":" in value:
        minutes, seconds = value.split(":", maxsplit=1)
        return int(minutes) + int(seconds) / 60
    numeric_value = float(value)
    return numeric_value / 60 if numeric_value > 120 else numeric_value
