"""Resolve cross-organization NHL/AHL assignments from official game logs."""

from __future__ import annotations

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from draft_room_intelligence.data.ahl_api import fetch_jsonp
from draft_room_intelligence.data.nhl_api import NHL_API_BASE_URL, fetch_json
from draft_room_intelligence.data.team_rosters import RosterPlayer


def enrich_cross_organization_assignment_dates(
    players: list[RosterPlayer],
    *,
    nhl_season: str,
    nhl_game_type: int = 2,
    cache_json_dir: str | Path | None = None,
) -> list[RosterPlayer]:
    """Attach latest official game dates only where organizations conflict."""
    collision_keys = {
        assignment_key(player)
        for group in cross_organization_groups(players)
        for player in group
        if not player.last_game_date
    }

    def load(player: RosterPlayer) -> tuple[tuple[str, str, str], str]:
        key = assignment_key(player)
        if key not in collision_keys:
            return key, player.last_game_date
        if player.league_level == "NHL":
            return key, latest_nhl_game_date(
                player,
                season=nhl_season,
                game_type=nhl_game_type,
                cache_json_dir=cache_json_dir,
            )
        if player.league_level == "AHL":
            return key, latest_ahl_game_date(player, cache_json_dir=cache_json_dir)
        return key, ""

    candidates = [player for player in players if assignment_key(player) in collision_keys]
    with ThreadPoolExecutor(max_workers=8) as executor:
        dates = dict(executor.map(load, candidates))
    return [
        replace(player, last_game_date=dates.get(assignment_key(player), player.last_game_date))
        if assignment_key(player) in collision_keys
        else player
        for player in players
    ]


def cross_organization_groups(players: list[RosterPlayer]) -> list[list[RosterPlayer]]:
    grouped: dict[str, list[RosterPlayer]] = {}
    for player in players:
        grouped.setdefault(compact_name(player.player_name), []).append(player)
    return [
        group
        for group in grouped.values()
        if len({player.team_id for player in group}) > 1 and contains_same_identity(group)
    ]


def latest_nhl_game_date(
    player: RosterPlayer,
    *,
    season: str,
    game_type: int,
    cache_json_dir: str | Path | None,
) -> str:
    player_id = source_player_id(player)
    if not player_id:
        return ""
    cache_path = cache_path_for(cache_json_dir, "nhl", f"{player_id}.{season}.{game_type}.json")
    payload = load_or_fetch_json(
        cache_path,
        lambda: fetch_json(f"{NHL_API_BASE_URL}/player/{player_id}/game-log/{season}/{game_type}"),
    )
    dates = [str(row.get("gameDate", "")) for row in payload.get("gameLog", []) if row.get("gameDate")]
    return max(dates, default="")


def latest_ahl_game_date(player: RosterPlayer, *, cache_json_dir: str | Path | None) -> str:
    season_id, team_code, player_id = ahl_source_parts(player.source_id)
    if not all((season_id, team_code, player_id)):
        return ""
    cache_path = cache_path_for(cache_json_dir, "ahl", f"{player_id}.{season_id}.json")
    payload = load_or_fetch_json(
        cache_path,
        lambda: fetch_jsonp(
            {
                "feed": "statviewfeed",
                "view": "player",
                "player_id": player_id,
                "season_id": season_id,
                "statsType": "standard",
            }
        ),
    )
    dates = []
    for game_group in payload.get("gameByGame", []):
        for section in game_group.get("sections", []):
            for item in section.get("data", []):
                row = item.get("row", {})
                teams = set(re.findall(r"[A-Z0-9]+", str(row.get("game", "")).upper()))
                if team_code in teams and row.get("date_played"):
                    dates.append(str(row["date_played"]))
    return max(dates, default="")


def load_or_fetch_json(cache_path: Path | None, fetcher) -> dict:
    if cache_path is not None and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    try:
        payload = fetcher()
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return payload


def cache_path_for(base_dir: str | Path | None, league: str, filename: str) -> Path | None:
    return Path(base_dir) / league / filename if base_dir else None


def assignment_key(player: RosterPlayer) -> tuple[str, str, str]:
    return player.league_level, player.source_id or player.player_id, player.team_id


def source_player_id(player: RosterPlayer) -> str:
    return player.source_id if player.source_id.isdigit() else player.player_id.removeprefix("nhl-")


def ahl_source_parts(source_id: str) -> tuple[str, str, str]:
    parts = source_id.split(":")
    return tuple(parts) if len(parts) == 3 else ("", "", "")


def compact_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if character.isascii() and character.isalnum())


def contains_same_identity(group: list[RosterPlayer]) -> bool:
    for index, left in enumerate(group):
        for right in group[index + 1 :]:
            if left.team_id != right.team_id and same_identity(left, right):
                return True
    return False


def same_identity(left: RosterPlayer, right: RosterPlayer) -> bool:
    if not left.age or not right.age:
        return False
    return abs(left.age - right.age) <= 1.0
