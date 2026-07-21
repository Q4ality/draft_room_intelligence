"""Normalize and apply auditable point-in-time NHL rights snapshots."""

from __future__ import annotations

import csv
import hashlib
import json
import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from draft_room_intelligence.data.nhl_contracts import (
    NHL_TEAM_IDS,
    normalize_player_id,
    normalize_team_id,
)
from draft_room_intelligence.data.team_rosters import (
    RosterPlayer,
    load_roster_csv,
    write_roster_csv,
)

SNAPSHOT_COLUMNS = [
    "team_id",
    "player_id",
    "player_name",
    "position",
    "league_level",
    "roster_status",
    "age",
    "effective_date",
    "snapshot_date",
    "source",
    "source_url",
]

RAW_COLUMN_ALIASES = {
    "team_id": ("team_id", "team", "club", "organization"),
    "player_id": ("player_id", "nhl_id", "id"),
    "player_name": ("player_name", "player", "name"),
    "position": ("position", "pos"),
    "league_level": ("league_level", "level", "roster_level"),
    "roster_status": ("roster_status", "status", "rights_status"),
    "age": ("age",),
    "effective_date": ("effective_date", "acquired_date", "transaction_date"),
}

METADATA_FIELDS = {
    "source",
    "source_url",
    "snapshot_date",
    "retrieved_at",
    "access_basis",
    "scope",
    "input_sha256",
}
REQUIRED_SCOPE = "full_league_rights_snapshot"
MINIMUM_SNAPSHOT_PLAYERS = 480
MINIMUM_PLAYERS_PER_TEAM = 10
POSITION_ALIASES = {"L": "LW", "R": "RW", "LD": "D", "RD": "D"}
VALID_POSITIONS = {"C", "LW", "RW", "D", "G"}


@dataclass(frozen=True)
class SnapshotNormalizationSummary:
    input_rows: int
    normalized_rows: int
    rejected_rows: int
    teams: int


@dataclass(frozen=True)
class SnapshotBuildSummary:
    source_rows: int
    output_players: int
    matched_players: int
    sparse_players: int
    excluded_base_players: int


def normalize_roster_snapshot(
    input_csv: str | Path,
    output_csv: str | Path,
    *,
    snapshot_date: str,
    metadata_json: str | Path,
    audit_csv: str | Path | None = None,
    minimum_team_count: int = 32,
    minimum_player_count: int = MINIMUM_SNAPSHOT_PLAYERS,
    minimum_players_per_team: int = MINIMUM_PLAYERS_PER_TEAM,
) -> SnapshotNormalizationSummary:
    cutoff = parse_iso_date(snapshot_date)
    metadata = read_snapshot_metadata(metadata_json, input_csv=input_csv, expected_snapshot=cutoff)
    with Path(input_csv).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = resolve_columns(reader.fieldnames or [])
        raw_rows = list(reader)
    missing = {"team_id", "player_name", "position", "league_level", "roster_status"} - set(columns)
    if missing:
        raise ValueError(
            f"raw roster snapshot missing mapped columns: {', '.join(sorted(missing))}"
        )

    candidates: list[tuple[int, dict[str, str], dict[str, str]]] = []
    audit_rows: list[dict[str, str]] = []
    for row_number, raw in enumerate(raw_rows, start=2):
        row, reason = normalize_snapshot_row(raw, columns, cutoff, metadata)
        if reason:
            audit_rows.append(audit_row(row_number, raw, columns, "rejected", reason))
            continue
        candidates.append((row_number, raw, row))

    accepted: list[dict[str, str]] = []
    id_counts = value_counts(row["player_id"] for _, _, row in candidates if row["player_id"])
    name_groups: dict[str, list[dict[str, str]]] = {}
    for _, _, row in candidates:
        name_groups.setdefault(compact_name(row["player_name"]), []).append(row)
    ambiguous_names = {
        name
        for name, rows in name_groups.items()
        if len(rows) > 1 and any(not row["player_id"] for row in rows)
    }
    for row_number, raw, row in candidates:
        player_id = row["player_id"]
        player_name = compact_name(row["player_name"])
        if (player_id and id_counts[player_id] > 1) or player_name in ambiguous_names:
            audit_rows.append(
                audit_row(row_number, raw, columns, "rejected", "conflicting_assignment")
            )
            continue
        accepted.append(row)
        audit_rows.append(audit_row(row_number, row, {}, "normalized", ""))

    team_ids = validate_snapshot_coverage(
        accepted,
        minimum_team_count=minimum_team_count,
        minimum_player_count=minimum_player_count,
        minimum_players_per_team=minimum_players_per_team,
    )
    accepted.sort(key=lambda row: (row["team_id"], row["player_name"]))
    write_csv(output_csv, SNAPSHOT_COLUMNS, accepted)
    if audit_csv is not None:
        write_csv(
            audit_csv,
            ["row_number", "status", "reason", "team_id", "player_id", "player_name"],
            audit_rows,
        )
    return SnapshotNormalizationSummary(
        input_rows=len(raw_rows),
        normalized_rows=len(accepted),
        rejected_rows=len(raw_rows) - len(accepted),
        teams=len(team_ids),
    )


def build_point_in_time_roster(
    base_roster_csv: str | Path,
    snapshot_csv: str | Path,
    output_csv: str | Path,
    *,
    expected_snapshot_date: str,
    audit_csv: str | Path | None = None,
    minimum_team_count: int = 32,
    minimum_player_count: int = MINIMUM_SNAPSHOT_PLAYERS,
    minimum_players_per_team: int = MINIMUM_PLAYERS_PER_TEAM,
) -> SnapshotBuildSummary:
    base_players = load_roster_csv(base_roster_csv)
    snapshot_rows = read_snapshot_rows(
        snapshot_csv,
        expected_snapshot_date=expected_snapshot_date,
        minimum_team_count=minimum_team_count,
        minimum_player_count=minimum_player_count,
        minimum_players_per_team=minimum_players_per_team,
    )
    by_id: dict[str, list[RosterPlayer]] = {}
    by_name: dict[str, list[RosterPlayer]] = {}
    team_names = {player.team_id: player.team_name for player in base_players if player.team_name}
    for player in base_players:
        source_id = roster_identity(player)
        if source_id:
            by_id.setdefault(source_id, []).append(player)
        by_name.setdefault(compact_name(player.player_name), []).append(player)

    output: list[RosterPlayer] = []
    used_base: set[tuple[str, str, str]] = set()
    audit_rows: list[dict[str, str]] = []
    matched = 0
    sparse = 0
    for row in snapshot_rows:
        candidates = match_base_players(row, by_id, by_name)
        if len(candidates) > 1:
            raise ValueError(f"ambiguous base-roster match for {row['player_name']}")
        if candidates:
            player = candidates[0]
            used_base.add(base_key(player))
            output.append(apply_snapshot(player, row, team_names))
            matched += 1
            audit_rows.append(build_audit_row(row, "matched_season_stats", player))
        else:
            output.append(sparse_snapshot_player(row, team_names))
            sparse += 1
            audit_rows.append(build_audit_row(row, "rights_holder_without_season_stats", None))

    for player in base_players:
        if base_key(player) not in used_base:
            audit_rows.append(excluded_audit_row(player))
    output.sort(
        key=lambda player: (
            player.team_id,
            player.league_level,
            player.position,
            player.player_name,
        )
    )
    write_roster_csv(output_csv, output)
    if audit_csv is not None:
        write_csv(
            audit_csv,
            ["status", "team_id", "player_id", "player_name", "base_team_id", "snapshot_date"],
            audit_rows,
        )
    return SnapshotBuildSummary(
        source_rows=len(snapshot_rows),
        output_players=len(output),
        matched_players=matched,
        sparse_players=sparse,
        excluded_base_players=len(base_players) - len(used_base),
    )


def normalize_snapshot_row(raw, columns, cutoff: date, metadata) -> tuple[dict[str, str], str]:
    def value(key: str) -> str:
        return (raw.get(columns.get(key, ""), "") or "").strip()

    team_id = normalize_team_id(value("team_id"))
    player_name = value("player_name")
    position = normalize_position(value("position"))
    league_level = value("league_level").upper()
    status = value("roster_status").lower().replace(" ", "_")
    effective = value("effective_date")
    if not team_id or team_id not in NHL_TEAM_IDS:
        return {}, "invalid_team"
    if not player_name:
        return {}, "missing_player_name"
    if not compact_name(player_name):
        return {}, "unmatchable_player_name"
    if position not in VALID_POSITIONS:
        return {}, "invalid_position"
    if league_level not in {"NHL", "AHL", "PROSPECT"}:
        return {}, "invalid_league_level"
    if not status:
        return {}, "missing_roster_status"
    try:
        effective_date = parse_iso_date(effective) if effective else None
        age = float(value("age")) if value("age") else 0.0
    except ValueError:
        return {}, "malformed_value"
    if effective_date and effective_date > cutoff:
        return {}, "future_assignment"
    return {
        "team_id": team_id,
        "player_id": normalize_player_id(value("player_id")),
        "player_name": player_name,
        "position": position,
        "league_level": league_level,
        "roster_status": status,
        "age": f"{age:.1f}" if age else "",
        "effective_date": effective,
        "snapshot_date": cutoff.isoformat(),
        "source": metadata["source"],
        "source_url": metadata["source_url"],
    }, ""


def read_snapshot_metadata(path, *, input_csv, expected_snapshot: date) -> dict[str, str]:
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("roster snapshot metadata must be a JSON object")
    missing = METADATA_FIELDS - set(values)
    if missing:
        raise ValueError(f"roster snapshot metadata missing fields: {', '.join(sorted(missing))}")
    if any(not isinstance(values[field], str) for field in METADATA_FIELDS):
        raise ValueError("roster snapshot metadata fields must be strings")
    if values["snapshot_date"] != expected_snapshot.isoformat():
        raise ValueError("roster snapshot metadata date does not match requested snapshot")
    if values["scope"] != REQUIRED_SCOPE:
        raise ValueError(f"roster snapshot metadata scope must be {REQUIRED_SCOPE}")
    required_values = (values["source"], values["source_url"], values["access_basis"])
    if not all(value.strip() for value in required_values):
        raise ValueError("roster snapshot metadata must document source, URL, and access basis")
    parse_iso_date(values["retrieved_at"][:10])
    if values["input_sha256"].lower() != file_sha256(input_csv):
        raise ValueError("roster snapshot metadata checksum does not match input CSV")
    return {key: str(value).strip() for key, value in values.items()}


def read_snapshot_rows(
    path,
    *,
    expected_snapshot_date: str,
    minimum_team_count: int = 32,
    minimum_player_count: int = MINIMUM_SNAPSHOT_PLAYERS,
    minimum_players_per_team: int = MINIMUM_PLAYERS_PER_TEAM,
) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = set(SNAPSHOT_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"normalized roster snapshot missing columns: {', '.join(sorted(missing))}"
            )
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    dates = {row["snapshot_date"] for row in rows}
    if len(dates) != 1 or not next(iter(dates), ""):
        raise ValueError("normalized roster snapshot must contain one non-empty snapshot date")
    if dates != {expected_snapshot_date}:
        raise ValueError("normalized roster snapshot date does not match expected snapshot")
    player_ids = [row["player_id"] for row in rows if row["player_id"]]
    name_groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        name_groups.setdefault(compact_name(row["player_name"]), []).append(row)
    ambiguous_name = any(
        len(group) > 1 and any(not row["player_id"] for row in group)
        for group in name_groups.values()
    )
    if len(player_ids) != len(set(player_ids)) or ambiguous_name:
        raise ValueError("normalized roster snapshot contains duplicate player assignments")
    validate_snapshot_coverage(
        rows,
        minimum_team_count=minimum_team_count,
        minimum_player_count=minimum_player_count,
        minimum_players_per_team=minimum_players_per_team,
    )
    return rows


def validate_snapshot_coverage(
    rows,
    *,
    minimum_team_count: int,
    minimum_player_count: int,
    minimum_players_per_team: int,
) -> set[str]:
    team_ids = {row["team_id"] for row in rows}
    if minimum_team_count > 0 and len(team_ids) < minimum_team_count:
        raise ValueError(
            f"roster snapshot covers {len(team_ids)} teams; "
            f"at least {minimum_team_count} are required"
        )
    if minimum_player_count > 0 and len(rows) < minimum_player_count:
        raise ValueError(
            f"roster snapshot contains {len(rows)} players; "
            f"at least {minimum_player_count} are required"
        )
    team_counts = value_counts(row["team_id"] for row in rows)
    thin_teams = sorted(
        team_id for team_id, count in team_counts.items() if count < minimum_players_per_team
    )
    if minimum_players_per_team > 0 and thin_teams:
        raise ValueError(
            f"roster snapshot teams below {minimum_players_per_team} players: "
            + ", ".join(thin_teams)
        )
    return team_ids


def match_base_players(row, by_id, by_name) -> list[RosterPlayer]:
    player_id = normalize_player_id(row["player_id"])
    candidates = (
        by_id.get(player_id, [])
        if player_id
        else by_name.get(compact_name(row["player_name"]), [])
    )
    target_name = compact_name(row["player_name"])
    if player_id and len(candidates) == 1:
        return candidates if compact_name(candidates[0].player_name) == target_name else []
    if len(candidates) <= 1:
        return candidates
    same_name = [player for player in candidates if compact_name(player.player_name) == target_name]
    if len(same_name) == 1:
        return same_name
    level = [player for player in same_name if player.league_level == row["league_level"]]
    return level if len(level) == 1 else same_name


def apply_snapshot(player: RosterPlayer, row, team_names) -> RosterPlayer:
    team_id = row["team_id"]
    level = row["league_level"]
    return replace(
        player,
        team_id=team_id,
        team_name=team_names.get(team_id, team_id),
        league_level=level,
        affiliate_of=player.affiliate_of if player.team_id == team_id and level == "AHL" else "",
        position=row["position"] or player.position,
        age=float(row["age"]) if row["age"] else player.age,
        snapshot_date=row["snapshot_date"],
        snapshot_type="point_in_time_rights",
        roster_status=row["roster_status"],
        assignment_confidence="high",
        assignment_source=row["source"],
        assignment_source_url=row["source_url"],
    )


def sparse_snapshot_player(row, team_names) -> RosterPlayer:
    return RosterPlayer(
        team_id=row["team_id"],
        team_name=team_names.get(row["team_id"], row["team_id"]),
        league_level=row["league_level"],
        affiliate_of="",
        player_id=f"snapshot-{row['player_id'] or compact_name(row['player_name'])}",
        player_name=row["player_name"],
        position=row["position"],
        age=float(row["age"]) if row["age"] else 0.0,
        snapshot_date=row["snapshot_date"],
        snapshot_type="point_in_time_rights",
        roster_status=row["roster_status"],
        assignment_confidence="high",
        assignment_source=row["source"],
        assignment_source_url=row["source_url"],
        source=row["source"],
        source_id=row["player_id"],
        source_url=row["source_url"],
    )


def resolve_columns(fieldnames) -> dict[str, str]:
    available = {normalize_column(name): name for name in fieldnames}
    return {
        canonical: available[normalize_column(alias)]
        for canonical, aliases in RAW_COLUMN_ALIASES.items()
        for alias in aliases
        if normalize_column(alias) in available
    }


def normalize_column(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def normalize_position(value: str) -> str:
    primary = value.strip().upper().replace("-", "/").split("/", maxsplit=1)[0]
    return POSITION_ALIASES.get(primary, primary)


def value_counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def roster_identity(player: RosterPlayer) -> str:
    return normalize_player_id(player.source_id or player.player_id)


def base_key(player: RosterPlayer) -> tuple[str, str, str]:
    return player.team_id, player.league_level, player.player_id


def compact_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if character.isalnum())


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_row(row_number, raw, columns, status, reason):
    def value(key):
        return (raw.get(columns.get(key, key), "") or "").strip()

    return {
        "row_number": str(row_number),
        "status": status,
        "reason": reason,
        "team_id": value("team_id"),
        "player_id": value("player_id"),
        "player_name": value("player_name"),
    }


def build_audit_row(row, status, base_player):
    return {
        "status": status,
        "team_id": row["team_id"],
        "player_id": row["player_id"],
        "player_name": row["player_name"],
        "base_team_id": base_player.team_id if base_player else "",
        "snapshot_date": row["snapshot_date"],
    }


def excluded_audit_row(player):
    return {
        "status": "excluded_not_in_rights_snapshot",
        "team_id": "",
        "player_id": roster_identity(player),
        "player_name": player.player_name,
        "base_team_id": player.team_id,
        "snapshot_date": "",
    }


def write_csv(path, columns, rows) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
