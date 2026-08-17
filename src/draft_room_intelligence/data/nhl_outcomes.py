"""Cache official NHL outcome inputs with draft-detail identity verification."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from draft_room_intelligence.data.nhl_draft import NHL_DRAFT_URL, localized, slugify
from draft_room_intelligence.reports.longitudinal_outcomes import (
    REQUIRED_COLUMNS,
    SUPPORTED_HORIZONS,
)

NHL_PLAYER_SEARCH_URL = (
    "https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=10&q={query}"
)
NHL_PLAYER_LANDING_URL = "https://api-web.nhle.com/v1/player/{player_id}/landing"


@dataclass(frozen=True)
class OutcomeCacheResult:
    draft_year: int
    cache_dir: Path
    matched_count: int
    unresolved_count: int


@dataclass(frozen=True)
class OutcomeRangeResult:
    results: tuple[OutcomeCacheResult, ...]


def collect_nhl_outcome_year(
    cache_root: str | Path,
    *,
    draft_year: int,
    refresh: bool = False,
    start_pick: int = 1,
    end_pick: int | None = None,
    overrides_path: str | Path | None = None,
) -> OutcomeCacheResult:
    if start_pick < 1:
        raise ValueError("start_pick must be positive")
    if end_pick is not None and end_pick < start_pick:
        raise ValueError("end_pick must be greater than or equal to start_pick")
    root = Path(cache_root) / str(draft_year)
    picks = fetch_cached_json(
        root / "draft_picks.json", NHL_DRAFT_URL.format(draft_year=draft_year), refresh
    )
    known_picks = {
        int(pick.get("overallPick") or 0)
        for pick in picks.get("picks", [])
        if int(pick.get("overallPick") or 0) > 0
    }
    overrides = load_identity_overrides(overrides_path, draft_year, known_picks)
    match_rows: list[dict[str, str]] = []
    for pick in picks.get("picks", []):
        overall_pick = int(pick.get("overallPick") or 0)
        if overall_pick < start_pick or (end_pick is not None and overall_pick > end_pick):
            continue
        name = pick_name(pick)
        if not overall_pick or not name:
            continue
        search_path = root / "search" / f"{overall_pick:03d}.json"
        candidates = fetch_cached_json(
            search_path,
            NHL_PLAYER_SEARCH_URL.format(query=quote(name)),
            refresh,
        )
        candidate_rows = candidates if isinstance(candidates, list) else []
        landings: dict[int, dict[str, object]] = {}
        for candidate in candidate_rows:
            player_id = int(candidate.get("playerId") or 0)
            if player_id:
                landings[player_id] = fetch_cached_json(
                    root / "players" / f"{player_id}.json",
                    NHL_PLAYER_LANDING_URL.format(player_id=player_id),
                    refresh,
                )
        override_id = overrides.get(overall_pick)
        if override_id:
            landings[override_id] = fetch_cached_json(
                root / "players" / f"{override_id}.json",
                NHL_PLAYER_LANDING_URL.format(player_id=override_id),
                refresh,
            )
        resolved_id = resolve_player_id(draft_year, overall_pick, landings)
        match_rows.append(
            {
                "draft_year": str(draft_year),
                "overall_pick": str(overall_pick),
                "player_id": f"{draft_year}-{overall_pick:03d}-{slugify(name)}",
                "draft_source_id": f"{draft_year}-{overall_pick}",
                "name": name,
                "nhl_player_id": str(resolved_id or ""),
                "status": "matched" if resolved_id else "unresolved",
            }
        )
    audit_path = root / "player_matches.csv"
    existing_rows = read_match_audit(audit_path)
    write_match_audit(audit_path, merge_match_rows(existing_rows, match_rows))
    return OutcomeCacheResult(
        draft_year=draft_year,
        cache_dir=root,
        matched_count=sum(row["status"] == "matched" for row in match_rows),
        unresolved_count=sum(row["status"] == "unresolved" for row in match_rows),
    )


def collect_nhl_outcome_range(
    cache_root: str | Path,
    *,
    start_year: int,
    end_year: int,
    batch_size: int = 10,
    refresh: bool = False,
    overrides_path: str | Path | None = None,
) -> OutcomeRangeResult:
    """Collect a bounded first batch for each year; rerun to advance by audit state."""

    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    results: list[OutcomeCacheResult] = []
    for draft_year in range(start_year, end_year + 1):
        start_pick = next_unreviewed_pick(Path(cache_root) / str(draft_year))
        results.append(
            collect_nhl_outcome_year(
                cache_root,
                draft_year=draft_year,
                refresh=refresh,
                start_pick=start_pick,
                end_pick=start_pick + batch_size - 1,
                overrides_path=overrides_path,
            )
        )
    return OutcomeRangeResult(tuple(results))


def resolve_player_id(
    draft_year: int, overall_pick: int, landings: dict[int, dict[str, object]]
) -> int | None:
    matches = [
        player_id
        for player_id, landing in landings.items()
        if draft_details_match(landing.get("draftDetails"), draft_year, overall_pick)
    ]
    return matches[0] if len(matches) == 1 else None


def draft_details_match(details: object, draft_year: int, overall_pick: int) -> bool:
    if not isinstance(details, dict):
        return False
    return details.get("year") == draft_year and details.get("overallPick") == overall_pick


def pick_name(pick: dict[str, object]) -> str:
    name_parts = (localized(pick.get("firstName")), localized(pick.get("lastName")))
    return " ".join(value for value in name_parts if value)


def fetch_cached_json(path: Path, url: str, refresh: bool) -> dict[str, object] | list[object]:
    if path.is_file() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    request = Request(url, headers={"User-Agent": "draft-room-intelligence/0.1"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed NHL public endpoints
        payload = json.load(response)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def write_match_audit(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "draft_year",
        "overall_pick",
        "player_id",
        "draft_source_id",
        "name",
        "nhl_player_id",
        "status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_match_audit(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def next_unreviewed_pick(cache_dir: Path) -> int:
    audit_path = cache_dir / "player_matches.csv"
    reviewed = {
        int(row["overall_pick"])
        for row in read_match_audit(audit_path)
        if row.get("overall_pick", "").isdigit()
    }
    draft_path = cache_dir / "draft_picks.json"
    if draft_path.is_file():
        payload = json.loads(draft_path.read_text(encoding="utf-8"))
        picks = sorted(
            int(row.get("overallPick") or 0)
            for row in payload.get("picks", [])
            if int(row.get("overallPick") or 0) > 0
        )
        fallback = picks[-1] + 1 if picks else 1
        return next((pick for pick in picks if pick not in reviewed), fallback)
    pick = 1
    while pick in reviewed:
        pick += 1
    return pick


def merge_match_rows(
    existing_rows: list[dict[str, str]], new_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    rows = {int(row["overall_pick"]): row for row in existing_rows}
    rows.update({int(row["overall_pick"]): row for row in new_rows})
    return [rows[pick] for pick in sorted(rows)]


def write_time_bounded_outcome_labels(
    cache_root: str | Path,
    output_root: str | Path,
    *,
    draft_year: int,
    horizons: tuple[int, ...] = SUPPORTED_HORIZONS,
    snapshot_dir: str | Path,
) -> list[Path]:
    """Aggregate cached NHL regular-season rows into canonical horizon labels."""

    cache_dir = Path(cache_root) / str(draft_year)
    matched = validated_matched_audit_rows(cache_dir / "player_matches.csv", draft_year)
    normalized_ids = normalized_player_ids(snapshot_dir, draft_year)
    matched_picks = {int(row["overall_pick"]) for row in matched}
    normalized_picks = set(normalized_ids)
    if matched_picks != normalized_picks:
        missing = sorted(normalized_picks - matched_picks)
        unexpected = sorted(matched_picks - normalized_picks)
        raise ValueError(
            f"cannot write partial canonical labels for {draft_year}: "
            f"missing picks={missing}; unexpected picks={unexpected}"
        )
    paths: list[Path] = []
    for horizon_years in horizons:
        rows = []
        for row in matched:
            overall_pick = int(row["overall_pick"])
            if overall_pick not in normalized_ids:
                raise ValueError(f"no normalized player ID for {draft_year} pick {overall_pick}")
            rows.append(
                build_outcome_label_from_cache(
                    row,
                    cache_dir,
                    draft_year,
                    horizon_years,
                    player_id=normalized_ids[overall_pick],
                )
            )
        path = Path(output_root) / str(draft_year) / f"{horizon_years}y.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        paths.append(path)
    return paths


def build_outcome_label_from_cache(
    match: dict[str, str],
    cache_dir: Path,
    draft_year: int,
    horizon_years: int,
    *,
    player_id: str | None = None,
) -> dict[str, str]:
    resolved_player_id = player_id or match["player_id"]
    nhl_player_id = match["nhl_player_id"]
    landing_path = cache_dir / "players" / f"{nhl_player_id}.json"
    landing = json.loads(landing_path.read_text(encoding="utf-8"))
    target_year = draft_year + horizon_years
    season_totals = landing.get("seasonTotals")
    if not isinstance(season_totals, list):
        raise ValueError(f"invalid seasonTotals cache for NHL player {nhl_player_id}")
    season_rows = []
    for row in season_totals:
        if not isinstance(row, dict):
            raise ValueError(f"invalid season row for NHL player {nhl_player_id}")
        if row.get("leagueAbbrev") != "NHL" or row.get("gameTypeId") != 2:
            continue
        if season_end_year(row.get("season")) <= target_year:
            season_rows.append(row)
    games = sum(required_nonnegative_int(row, "gamesPlayed", nhl_player_id) for row in season_rows)
    points = sum(points_for_season(row, nhl_player_id) for row in season_rows)
    starts = sum(
        optional_nonnegative_int(row, "gamesStarted", nhl_player_id) for row in season_rows
    )
    toi_minutes = sum(toi_minutes_for_season(row, nhl_player_id) for row in season_rows)
    return {
        "player_id": resolved_player_id,
        "draft_year": str(draft_year),
        "horizon_years": str(horizon_years),
        "outcome_through": f"{target_year}-06-30",
        "nhl_games": str(games),
        "nhl_points": str(points),
        "nhl_toi_minutes": f"{toi_minutes:.1f}",
        "goalie_starts": str(starts),
        "value_proxy": "",
        "source": "nhl_public_api",
        "source_id": nhl_player_id,
        "source_url": NHL_PLAYER_LANDING_URL.format(player_id=nhl_player_id),
    }


def season_end_year(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("invalid NHL season identifier")
    season = str(value or "")
    if not season.isdigit() or len(season) != 8:
        raise ValueError("invalid NHL season identifier")
    start_year = int(season[:4])
    end_year = int(season[4:])
    if end_year != start_year + 1:
        raise ValueError("invalid NHL season identifier")
    return end_year


def required_nonnegative_int(row: dict[str, object], field: str, player_id: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or value is None:
        raise ValueError(f"invalid {field} for NHL player {player_id}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field} for NHL player {player_id}") from exc
    if parsed < 0:
        raise ValueError(f"invalid {field} for NHL player {player_id}")
    return parsed


def optional_nonnegative_int(row: dict[str, object], field: str, player_id: str) -> int:
    if row.get(field) in (None, ""):
        return 0
    return required_nonnegative_int(row, field, player_id)


def toi_minutes_for_season(row: dict[str, object], player_id: str) -> float:
    games = required_nonnegative_int(row, "gamesPlayed", player_id)
    if games == 0:
        return 0.0
    if "gamesStarted" in row:
        return average_toi_minutes(str(row.get("timeOnIce") or ""), player_id)
    return games * average_toi_minutes(str(row.get("avgToi") or ""), player_id)


def points_for_season(row: dict[str, object], player_id: str) -> int:
    if "gamesStarted" in row and row.get("points") in (None, ""):
        return 0
    return required_nonnegative_int(row, "points", player_id)


def average_toi_minutes(value: str, player_id: str) -> float:
    try:
        minutes, seconds = value.split(":", maxsplit=1)
        parsed_minutes = int(minutes)
        parsed_seconds = int(seconds)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid avgToi for NHL player {player_id}") from exc
    if parsed_minutes < 0 or not 0 <= parsed_seconds < 60:
        raise ValueError(f"invalid avgToi for NHL player {player_id}")
    return parsed_minutes + parsed_seconds / 60


def load_identity_overrides(
    path: str | Path | None, draft_year: int, known_picks: set[int]
) -> dict[int, int]:
    if path is None:
        return {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"draft_year", "overall_pick", "nhl_player_id", "reason", "source_url"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError("identity override file is missing required columns")
        rows = list(reader)
    overrides: dict[int, int] = {}
    for row in rows:
        try:
            row_year = int(row.get("draft_year") or 0)
            overall_pick = int(row.get("overall_pick") or 0)
            player_id = int(row.get("nhl_player_id") or 0)
        except ValueError as exc:
            raise ValueError("identity override has invalid numeric values") from exc
        if row_year != draft_year:
            continue
        if overall_pick <= 0 or player_id <= 0 or overall_pick not in known_picks:
            raise ValueError(f"identity override has invalid pick or player ID: {overall_pick}")
        if not (row.get("reason") or "").strip() or not (row.get("source_url") or "").startswith(
            "https://"
        ):
            raise ValueError(f"identity override lacks provenance for pick {overall_pick}")
        if overall_pick in overrides:
            raise ValueError(f"duplicate identity override for {draft_year} pick {overall_pick}")
        overrides[overall_pick] = player_id
    return overrides


def normalized_player_ids(snapshot_dir: str | Path, draft_year: int) -> dict[int, str]:
    selections_path = Path(snapshot_dir) / "draft_selections.csv"
    with selections_path.open(newline="", encoding="utf-8-sig") as handle:
        selections = list(csv.DictReader(handle))
    mapping: dict[int, str] = {}
    for row in selections:
        if int(row.get("draft_year") or 0) != draft_year:
            continue
        overall_pick = int(row.get("overall_pick") or 0)
        player_id = (row.get("player_id") or "").strip()
        if overall_pick <= 0 or not player_id or overall_pick in mapping:
            raise ValueError(f"invalid normalized player mapping for {draft_year}")
        mapping[overall_pick] = player_id
    if not mapping:
        raise ValueError(f"no draft selections for {draft_year}: {selections_path}")
    return mapping


def validated_matched_audit_rows(path: Path, draft_year: int) -> list[dict[str, str]]:
    required_columns = {
        "draft_year",
        "overall_pick",
        "player_id",
        "draft_source_id",
        "name",
        "nhl_player_id",
        "status",
    }
    rows = read_match_audit(path)
    matched: list[dict[str, str]] = []
    seen_picks: set[int] = set()
    for row in rows:
        if row.get("status") != "matched":
            continue
        if not required_columns.issubset(row) or int(row.get("draft_year") or 0) != draft_year:
            raise ValueError(f"invalid match audit row in {path}")
        try:
            overall_pick = int(row.get("overall_pick") or 0)
            nhl_player_id = int(row.get("nhl_player_id") or 0)
        except ValueError as exc:
            raise ValueError(f"invalid match audit row in {path}") from exc
        if overall_pick <= 0 or nhl_player_id <= 0 or not (row.get("player_id") or "").strip():
            raise ValueError(f"invalid match audit row in {path}")
        if overall_pick in seen_picks:
            raise ValueError(f"duplicate matched pick in {path}: {overall_pick}")
        seen_picks.add(overall_pick)
        matched.append(row)
    return matched
