"""Import NHL roster and club-stat payloads into normalized team roster rows."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
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
    cache_json_dir: str | Path | None = None,
    as_of: date | None = None,
) -> NhlRosterImportSummary:
    """Load NHL roster rows from cached JSON or the public NHL API."""

    teams = normalize_team_codes(team_codes or list(NHL_TEAM_NAMES))
    players: list[RosterPlayer] = []
    teams_loaded = 0
    stats_loaded = 0
    for team_code in teams:
        roster_payload = load_roster_payload(
            team_code,
            season=season,
            roster_json_dir=roster_json_dir,
            cache_json_dir=cache_json_dir,
        )
        stats_payload = load_stats_payload(
            team_code,
            season=season,
            game_type=game_type,
            stats_json_dir=stats_json_dir,
            cache_json_dir=cache_json_dir,
        )
        if season and not stats_payload:
            raise ValueError(f"historical NHL import requires club stats for {team_code} {season}")
        if stats_payload:
            stats_loaded += 1
        reference_date = as_of or season_reference_date(season)
        if season and stats_payload:
            landing_payloads = load_missing_player_landings(
                roster_payload,
                stats_payload,
                cache_json_dir=cache_json_dir,
                allow_fetch=roster_json_dir is None,
            )
            team_players = parse_nhl_season_stats_payload(
                team_code,
                stats_payload,
                roster_payload=roster_payload,
                landing_payloads=landing_payloads,
                as_of=reference_date,
            )
        else:
            team_players = parse_nhl_roster_payload(
                team_code,
                roster_payload,
                stats_payload=stats_payload,
                as_of=reference_date,
                snapshot_type="current_roster",
            )
        if team_players:
            teams_loaded += 1
        players.extend(team_players)

    if season:
        players = resolve_season_assignments(
            players,
            season=season,
            game_type=game_type,
            cache_json_dir=cache_json_dir,
            allow_fetch=roster_json_dir is None,
        )

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
    snapshot_type: str = "current_roster",
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
            shots_against = int_value(first_value(stats, "shotsAgainst", "shots_against", "sa"))
            saves = int_value(first_value(stats, "saves", "sv"))
            goals_against = int_value(first_value(stats, "goalsAgainst", "goals_against", "ga"))
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
                    goalie_minutes=goalie_minutes(stats),
                    goalie_wins=int_value(first_value(stats, "wins", "w")),
                    goalie_saves=saves,
                    goalie_shots_against=shots_against,
                    goalie_goals_against=goals_against,
                    goalie_save_percentage=goalie_save_percentage(stats, saves=saves, shots_against=shots_against),
                    goalie_goals_against_average=optional_float_value(
                        first_value(
                            stats,
                            "goalsAgainstAverage",
                            "goalAgainstAverage",
                            "goalieGoalsAgainstAverage",
                            "gaa",
                        )
                    ),
                    goalie_shutouts=int_value(first_value(stats, "shutouts", "so")),
                    snapshot_date=(as_of or date.today()).isoformat(),
                    snapshot_type=snapshot_type,
                    roster_status="season_roster" if snapshot_type == "season_roster" else "active_roster",
                    assignment_confidence="medium" if snapshot_type == "season_roster" else "high",
                    source="nhl_api_season_roster" if snapshot_type == "season_roster" else "nhl_api",
                    source_id=player_id,
                    source_url=f"{NHL_API_BASE_URL}/player/{player_id}/landing",
                )
            )
    return players


def parse_nhl_season_stats_payload(
    team_code: str,
    stats_payload: dict,
    *,
    roster_payload: dict | None = None,
    landing_payloads: dict[str, dict] | None = None,
    as_of: date | None = None,
) -> list[RosterPlayer]:
    team_id = team_code.upper()
    team_name = NHL_TEAM_NAMES.get(team_id, team_id)
    roster_by_id = roster_players_by_id(roster_payload or {})
    landing_by_id = landing_payloads or {}
    players: list[RosterPlayer] = []
    for collection_key, default_position in (("skaters", ""), ("goalies", "G")):
        for stats in stats_payload.get(collection_key, []) or []:
            player_id = str(first_value(stats, "playerId", "id") or "")
            if not player_id:
                continue
            bio = roster_by_id.get(player_id, {}) or landing_by_id.get(player_id, {})
            position = str(
                first_value(stats, "positionCode", "position")
                or first_value(bio, "positionCode", "position")
                or default_position
            )
            games = int_value(first_value(stats, "gamesPlayed", "games", "gp"))
            shots_against = int_value(first_value(stats, "shotsAgainst", "shots_against", "sa"))
            saves = int_value(first_value(stats, "saves", "sv"))
            goals_against = int_value(first_value(stats, "goalsAgainst", "goals_against", "ga"))
            players.append(
                RosterPlayer(
                    team_id=team_id,
                    team_name=team_name,
                    league_level="NHL",
                    affiliate_of="",
                    player_id=f"nhl-{player_id}",
                    player_name=player_name(bio, stats),
                    position=position,
                    handedness=str(first_value(bio, "shootsCatches", "shoots") or "").upper(),
                    age=age_from_birth_date(str(first_value(bio, "birthDate") or ""), as_of=as_of),
                    height_cm=inches_to_cm(int_value(first_value(bio, "heightInInches"))),
                    weight_kg=pounds_to_kg(int_value(first_value(bio, "weightInPounds"))),
                    games=games,
                    goals=int_value(first_value(stats, "goals", "g")),
                    assists=int_value(first_value(stats, "assists", "a")),
                    points=int_value(first_value(stats, "points", "p")),
                    plus_minus=optional_int_value(first_value(stats, "plusMinus", "plusminus")),
                    time_on_ice_per_game=time_on_ice_minutes(
                        first_value(stats, "timeOnIcePerGame", "avgTimeOnIcePerGame", "avgTimeOnIce", "toiPerGame")
                    ),
                    goalie_minutes=goalie_minutes(stats),
                    goalie_wins=int_value(first_value(stats, "wins", "w")),
                    goalie_saves=saves,
                    goalie_shots_against=shots_against,
                    goalie_goals_against=goals_against,
                    goalie_save_percentage=goalie_save_percentage(stats, saves=saves, shots_against=shots_against),
                    goalie_goals_against_average=optional_float_value(
                        first_value(stats, "goalsAgainstAverage", "goalAgainstAverage", "goalieGoalsAgainstAverage", "gaa")
                    ),
                    goalie_shutouts=int_value(first_value(stats, "shutouts", "so")),
                    snapshot_date=(as_of or date.today()).isoformat(),
                    snapshot_type="season_participation",
                    roster_status="season_participant",
                    assignment_confidence="medium",
                    source="nhl_api_club_stats",
                    source_id=player_id,
                    source_url=f"{NHL_API_BASE_URL}/player/{player_id}/landing",
                )
            )
    return players


def roster_players_by_id(payload: dict) -> dict[str, dict]:
    return {
        str(first_value(player, "id", "playerId")): player
        for group in ("forwards", "defensemen", "goalies")
        for player in payload.get(group, []) or []
        if first_value(player, "id", "playerId") is not None
    }


def load_missing_player_landings(
    roster_payload: dict,
    stats_payload: dict,
    *,
    cache_json_dir: str | Path | None,
    allow_fetch: bool,
) -> dict[str, dict]:
    roster_ids = set(roster_players_by_id(roster_payload))
    stat_ids = {
        str(first_value(row, "playerId", "id"))
        for key in ("skaters", "goalies")
        for row in stats_payload.get(key, []) or []
        if first_value(row, "playerId", "id") is not None
    }
    missing_ids = sorted(stat_ids - roster_ids)
    if not missing_ids:
        return {}

    def load(player_id: str) -> tuple[str, dict]:
        cache_path = Path(cache_json_dir) / "players" / f"{player_id}.landing.json" if cache_json_dir else None
        if cache_path is not None and cache_path.exists():
            return player_id, read_json_payload(cache_path)
        if not allow_fetch:
            return player_id, {}
        try:
            payload = fetch_json(f"{NHL_API_BASE_URL}/player/{player_id}/landing")
        except (OSError, ValueError):
            return player_id, {}
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return player_id, payload

    with ThreadPoolExecutor(max_workers=8) as executor:
        return dict(executor.map(load, missing_ids))


def resolve_season_assignments(
    players: list[RosterPlayer],
    *,
    season: str,
    game_type: int,
    cache_json_dir: str | Path | None,
    allow_fetch: bool,
) -> list[RosterPlayer]:
    grouped: dict[str, list[RosterPlayer]] = {}
    for player in players:
        grouped.setdefault(player.source_id, []).append(player)
    duplicate_ids = sorted(player_id for player_id, group in grouped.items() if player_id and len(group) > 1)

    def load_last_team(player_id: str) -> tuple[str, str]:
        cache_path = (
            Path(cache_json_dir) / "players" / f"{player_id}.{season}.{game_type}.game-log.json"
            if cache_json_dir
            else None
        )
        if cache_path is not None and cache_path.exists():
            payload = read_json_payload(cache_path)
        elif allow_fetch:
            try:
                payload = fetch_json(f"{NHL_API_BASE_URL}/player/{player_id}/game-log/{season}/{game_type}")
            except (OSError, ValueError):
                payload = {}
            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        else:
            payload = {}
        game_log = payload.get("gameLog", []) or []
        latest = max(game_log, key=lambda row: (str(row.get("gameDate", "")), int(row.get("gameId", 0)))) if game_log else {}
        return player_id, str(latest.get("teamAbbrev", "")).upper()

    with ThreadPoolExecutor(max_workers=8) as executor:
        last_teams = dict(executor.map(load_last_team, duplicate_ids))

    resolved: list[RosterPlayer] = []
    for player_id, group in grouped.items():
        if len(group) == 1:
            resolved.extend(group)
            continue
        last_team = last_teams.get(player_id, "")
        matching = [player for player in group if player.team_id == last_team]
        if matching:
            resolved.append(max(matching, key=lambda player: player.games))
        else:
            fallback = max(group, key=lambda player: player.games)
            resolved.append(
                replace(
                    fallback,
                    assignment_confidence="low",
                    roster_status="season_participant_unresolved_assignment",
                )
            )
    return sorted(resolved, key=lambda player: (player.team_id, player.position, player.player_name))


def load_roster_payload(
    team_code: str,
    *,
    season: str,
    roster_json_dir: str | Path | None,
    cache_json_dir: str | Path | None = None,
) -> dict:
    if roster_json_dir is not None:
        base_dir = Path(roster_json_dir)
        candidates = [base_dir / f"{team_code.upper()}.{season}.roster.json"] if season else []
        if not season:
            candidates.append(base_dir / f"{team_code.upper()}.roster.json")
        for path in candidates:
            if path.exists():
                return read_json_payload(path)
        raise FileNotFoundError(candidates[0])
    roster_period = season or "current"
    cached_path = Path(cache_json_dir) / f"{team_code.upper()}.{roster_period}.roster.json" if cache_json_dir else None
    if cached_path is not None and cached_path.exists():
        return read_json_payload(cached_path)
    payload = fetch_json(f"{NHL_API_BASE_URL}/roster/{team_code.upper()}/{roster_period}")
    cache_payload(cache_json_dir, f"{team_code.upper()}.{roster_period}.roster.json", payload)
    return payload


def load_stats_payload(
    team_code: str,
    *,
    season: str,
    game_type: int,
    stats_json_dir: str | Path | None,
    cache_json_dir: str | Path | None = None,
) -> dict:
    if stats_json_dir is not None:
        base_dir = Path(stats_json_dir)
        candidates = [base_dir / f"{team_code.upper()}.{season}.{game_type}.stats.json"] if season else []
        if not season:
            candidates.append(base_dir / f"{team_code.upper()}.stats.json")
        for path in candidates:
            if path.exists():
                return read_json_payload(path)
        return {}
    if not season:
        return {}
    cached_path = Path(cache_json_dir) / f"{team_code.upper()}.{season}.{game_type}.stats.json" if cache_json_dir else None
    if cached_path is not None and cached_path.exists():
        return read_json_payload(cached_path)
    payload = fetch_json(f"{NHL_API_BASE_URL}/club-stats/{team_code.upper()}/{season}/{game_type}")
    cache_payload(cache_json_dir, f"{team_code.upper()}.{season}.{game_type}.stats.json", payload)
    return payload


def cache_payload(cache_json_dir: str | Path | None, filename: str, payload: dict) -> None:
    if cache_json_dir is None:
        return
    output_dir = Path(cache_json_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def season_reference_date(season: str) -> date | None:
    if len(season) != 8 or not season.isdigit():
        return None
    return date(int(season[4:]), 6, 1)


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


def optional_float_value(value) -> float | None:
    if value in ("", None):
        return None
    return float(value)


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


def goalie_minutes(stats: dict) -> float | None:
    value = first_value(stats, "minutes", "minutesPlayed", "goalieMinutes")
    if value not in ("", None):
        return time_on_ice_minutes(value)
    games = int_value(first_value(stats, "gamesPlayed", "games", "gp"))
    time_on_ice = time_on_ice_minutes(
        first_value(stats, "timeOnIcePerGame", "avgTimeOnIcePerGame", "avgTimeOnIce", "toiPerGame")
    )
    return round(games * time_on_ice, 2) if games and time_on_ice is not None else None


def goalie_save_percentage(stats: dict, *, saves: int, shots_against: int) -> float | None:
    value = optional_float_value(
        first_value(
            stats,
            "savePctg",
            "savePercentage",
            "savePct",
            "save_percentage",
            "svPct",
        )
    )
    if value is not None:
        return value / 100 if value > 1.0 else value
    return saves / shots_against if saves and shots_against else None
