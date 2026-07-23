"""Collect and normalize official NHL draft-pick payloads."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from draft_room_intelligence.data.eliteprospects_csv import ADVANCED_STAT_LINE_COLUMNS
from draft_room_intelligence.data.league_standardization import normalize_league_name

NHL_DRAFT_URL = "https://api-web.nhle.com/v1/draft/picks/{draft_year}/all"


@dataclass(frozen=True)
class NhlDraftCollectionResult:
    draft_year: int
    status: str
    cache_path: Path
    pick_count: int


def collect_nhl_draft_range(
    cache_root: str | Path,
    *,
    start_year: int,
    end_year: int,
    refresh: bool = False,
) -> list[NhlDraftCollectionResult]:
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")
    return [
        collect_nhl_draft_year(cache_root, draft_year=year, refresh=refresh)
        for year in range(start_year, end_year + 1)
    ]


def collect_nhl_draft_year(
    cache_root: str | Path,
    *,
    draft_year: int,
    refresh: bool = False,
) -> NhlDraftCollectionResult:
    cache_path = Path(cache_root) / str(draft_year) / "picks.json"
    if cache_path.is_file() and not refresh:
        payload = read_payload(cache_path)
        validate_payload(payload, draft_year)
        return NhlDraftCollectionResult(
            draft_year,
            "cached",
            cache_path,
            len(payload.get("picks", [])),
        )

    request = Request(
        NHL_DRAFT_URL.format(draft_year=draft_year),
        headers={"User-Agent": "draft-room-intelligence/0.1"},
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed official NHL endpoint
        payload = json.load(response)
    validate_payload(payload, draft_year)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(cache_path)
    return NhlDraftCollectionResult(
        draft_year,
        "downloaded",
        cache_path,
        len(payload["picks"]),
    )


def generate_nhl_draft_base_tables(
    draft_json_path: str | Path,
    output_dir: str | Path,
    *,
    draft_year: int,
) -> Path:
    payload = read_payload(Path(draft_json_path))
    validate_payload(payload, draft_year)
    picks = [raw for raw in payload.get("picks", []) if is_player_pick(raw)]
    if not picks:
        raise ValueError(f"no draft picks found for {draft_year}")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = [normalize_pick(raw, draft_year) for raw in picks]
    write_csv(root / "players.csv", player_fields(), [row["player"] for row in rows])
    write_csv(
        root / "draft_selections.csv",
        selection_fields(),
        [row["selection"] for row in rows],
    )
    write_csv(root / "rankings.csv", ranking_fields(), [row["ranking"] for row in rows])
    write_csv(root / "season_stat_lines.csv", stat_line_fields(), [])
    write_csv(root / "advanced_stat_lines.csv", ADVANCED_STAT_LINE_COLUMNS, [])
    # The draft feed has no observed NHL outcomes. Empty rows preserve unknown values.
    write_csv(root / "nhl_outcomes.csv", outcome_fields(), [])
    return root


def backfill_nhl_draft_player_fields(
    dataset_dir: str | Path,
    draft_json_path: str | Path,
    *,
    draft_year: int,
) -> int:
    """Fill blank normalized player fields from the official NHL draft payload."""
    payload = read_payload(Path(draft_json_path))
    validate_payload(payload, draft_year)
    official = {
        row["player"]["player_id"]: row["player"]
        for raw in payload.get("picks", [])
        if is_player_pick(raw)
        for row in [normalize_pick(raw, draft_year)]
    }
    players_path = Path(dataset_dir) / "players.csv"
    with players_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        players = list(reader)
        columns = list(reader.fieldnames or player_fields())
    updated = 0
    for player in players:
        source = official.get(player.get("player_id", ""))
        if not source:
            continue
        changed = False
        for field in ("nationality", "position", "height_cm", "weight_kg"):
            if not player.get(field) and source.get(field):
                player[field] = str(source[field])
                changed = True
        if changed:
            player["source"] = append_source(player.get("source", ""), "nhl_draft_api")
            updated += 1
    write_csv(players_path, columns, players)
    return updated


def append_source(existing: str, source: str) -> str:
    values = [value.strip() for value in existing.split(";") if value.strip()]
    if source not in values:
        values.append(source)
    return "; ".join(values)


def normalize_pick(raw: dict[str, object], draft_year: int) -> dict[str, dict[str, object]]:
    overall_pick = int(raw.get("overallPick") or 0)
    position = str(raw.get("positionCode") or "")
    name = " ".join(
        part
        for part in (localized(raw.get("firstName")), localized(raw.get("lastName")))
        if part
    ).strip()
    if not overall_pick or not name or not position:
        raise ValueError(
            f"invalid NHL draft row for {draft_year}: pick={overall_pick}, name={name!r}"
        )
    player_id = f"{draft_year}-{overall_pick:03d}-{slugify(name)}"
    source_id = f"{draft_year}-{overall_pick}"
    source_url = NHL_DRAFT_URL.format(draft_year=draft_year)
    league = normalize_league_name(str(raw.get("amateurLeague") or ""))
    common_source = {
        "source": "nhl_draft_api",
        "source_id": source_id,
        "source_url": source_url,
    }
    return {
        "player": {
            **common_source,
            "player_id": player_id,
            "name": name,
            "birth_date": "",
            "nationality": str(raw.get("countryCode") or ""),
            "position": position,
            "handedness": "",
            "height_cm": inches_to_cm(raw.get("height")),
            "weight_kg": pounds_to_kg(raw.get("weight")),
            "age_at_draft": "",
        },
        "selection": {
            **common_source,
            "player_id": player_id,
            "draft_year": str(draft_year),
            "team_id": str(raw.get("teamAbbrev") or ""),
            "team_name": localized(raw.get("teamName")),
            "round_number": str(raw.get("round") or ""),
            "overall_pick": str(overall_pick),
            "drafted_from_team": str(raw.get("amateurClubName") or ""),
            "drafted_from_league": league,
        },
        "ranking": {
            "player_id": player_id,
            "draft_year": str(draft_year),
            "source": "draft_slot_proxy",
            "rank": str(overall_pick),
            "scope": "all_drafted_players",
            "position": position,
            "source_id": source_id,
            "source_url": source_url,
        },
    }


def is_player_pick(raw: dict[str, object]) -> bool:
    name = " ".join(
        part
        for part in (localized(raw.get("firstName")), localized(raw.get("lastName")))
        if part
    ).strip()
    return (
        bool(str(raw.get("positionCode") or "").strip())
        and name.casefold() != "forfeited"
    )


def read_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload(payload: dict[str, object], draft_year: int) -> None:
    payload_year = int(payload.get("draftYear") or 0)
    if payload_year != draft_year:
        raise ValueError(
            f"NHL draft payload year {payload_year} does not match requested {draft_year}"
        )
    if not isinstance(payload.get("picks"), list):
        raise ValueError("NHL draft payload is missing picks list")


def localized(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("default") or "")
    return str(value or "")


def inches_to_cm(value: object) -> str:
    inches = int(value or 0)
    return str(round(inches * 2.54)) if inches else ""


def pounds_to_kg(value: object) -> str:
    pounds = int(value or 0)
    return str(round(pounds * 0.45359237)) if pounds else ""


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def player_fields() -> list[str]:
    return [
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
    ]


def selection_fields() -> list[str]:
    return [
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
    ]


def ranking_fields() -> list[str]:
    return [
        "player_id",
        "draft_year",
        "source",
        "rank",
        "scope",
        "position",
        "source_id",
        "source_url",
    ]


def stat_line_fields() -> list[str]:
    return [
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
    ]


def outcome_fields() -> list[str]:
    return [
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
    ]
