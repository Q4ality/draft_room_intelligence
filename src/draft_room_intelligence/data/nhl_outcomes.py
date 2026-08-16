"""Cache official NHL outcome inputs with draft-detail identity verification."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from draft_room_intelligence.data.nhl_draft import NHL_DRAFT_URL, localized, slugify

NHL_PLAYER_SEARCH_URL = "https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=10&q={query}"
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
) -> OutcomeCacheResult:
    if start_pick < 1:
        raise ValueError("start_pick must be positive")
    if end_pick is not None and end_pick < start_pick:
        raise ValueError("end_pick must be greater than or equal to start_pick")
    root = Path(cache_root) / str(draft_year)
    picks = fetch_cached_json(
        root / "draft_picks.json", NHL_DRAFT_URL.format(draft_year=draft_year), refresh
    )
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
    return " ".join(
        value for value in name_parts if value
    )


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
