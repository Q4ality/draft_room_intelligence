"""Overlay cached NHL contract and cap evidence onto normalized roster rows."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from draft_room_intelligence.data.team_rosters import (
    RosterPlayer,
    load_roster_csv,
    write_roster_csv,
)

CONTRACT_REQUIRED_COLUMNS = {
    "team_id",
    "player_name",
    "cap_hit",
    "contract_end_year",
    "snapshot_date",
}

NORMALIZED_CONTRACT_COLUMNS = [
    "team_id",
    "player_id",
    "player_name",
    "cap_hit",
    "contract_end_year",
    "contract_years_remaining",
    "contract_type",
    "trade_protection",
    "snapshot_date",
    "source",
    "source_url",
]

RAW_COLUMN_ALIASES = {
    "team_id": ("team_id", "team", "tm", "club"),
    "player_id": ("player_id", "nhl_id", "id"),
    "player_name": ("player_name", "player.name", "player", "name"),
    "cap_hit": ("cap_hit", "cap hit", "aav", "average_annual_value"),
    "contract_end_year": ("contract_end_year", "end", "end_year", "expiry_year"),
    "contract_years_remaining": ("contract_years_remaining", "years_remaining"),
    "contract_type": ("contract_type", "expiry", "status"),
    "trade_protection": ("trade_protection", "terms", "clauses"),
    "signed_date": ("signed_date", "signed", "signing_date", "date"),
}

TEAM_ALIASES = {
    "ANAHEIMDUCKS": "ANA",
    "BOSTONBRUINS": "BOS",
    "BUFFALOSABRES": "BUF",
    "CALGARYFLAMES": "CGY",
    "CAROLINAHURRICANES": "CAR",
    "CHICAGOBLACKHAWKS": "CHI",
    "COLORADOAVALANCHE": "COL",
    "COLUMBUSBLUEJACKETS": "CBJ",
    "DALLASSTARS": "DAL",
    "DETROITREDWINGS": "DET",
    "EDMONTONOILERS": "EDM",
    "FLORIDAPANTHERS": "FLA",
    "LOSANGELESKINGS": "LAK",
    "MINNESOTAWILD": "MIN",
    "MONTREALCANADIENS": "MTL",
    "NASHVILLEPREDATORS": "NSH",
    "NEWJERSEYDEVILS": "NJD",
    "NEWYORKISLANDERS": "NYI",
    "NEWYORKRANGERS": "NYR",
    "OTTAWASENATORS": "OTT",
    "PHILADELPHIAFLYERS": "PHI",
    "PITTSBURGHPENGUINS": "PIT",
    "SANJOSESHARKS": "SJS",
    "SEATTLEKRAKEN": "SEA",
    "STLOUISBLUES": "STL",
    "TAMPABAYLIGHTNING": "TBL",
    "TORONTOMAPLELEAFS": "TOR",
    "UTAHHOCKEYCLUB": "UTA",
    "UTAHMAMMOTH": "UTA",
    "VANCOUVERCANUCKS": "VAN",
    "VEGASGOLDENKNIGHTS": "VGK",
    "WASHINGTONCAPITALS": "WSH",
    "WINNIPEGJETS": "WPG",
}
NHL_TEAM_IDS = set(TEAM_ALIASES.values())
MIN_PLAUSIBLE_CAP_HIT = 500_000
MAX_PLAUSIBLE_CAP_HIT = 25_000_000
SOURCE_METADATA_REQUIRED_FIELDS = {
    "source",
    "source_url",
    "snapshot_date",
    "retrieved_at",
    "access_basis",
    "input_sha256",
}


@dataclass(frozen=True)
class ContractOverlaySummary:
    roster_players: int
    eligible_nhl_players: int
    contract_rows: int
    matched_players: int
    matched_nhl_players: int
    unmatched_contracts: int
    ambiguous_contracts: int

    @property
    def nhl_coverage(self) -> float:
        if not self.eligible_nhl_players:
            return 0.0
        return self.matched_nhl_players / self.eligible_nhl_players


@dataclass(frozen=True)
class ContractNormalizationSummary:
    input_rows: int
    normalized_rows: int
    rejected_rows: int
    future_signing_rows: int
    conflicting_duplicate_rows: int


@dataclass(frozen=True)
class ContractSourceMetadata:
    source: str
    source_url: str
    snapshot_date: str
    retrieved_at: str
    access_basis: str
    input_sha256: str


def enrich_roster_contracts(
    roster_csv: str | Path,
    contracts_csv: str | Path,
    output_csv: str | Path,
    *,
    audit_csv: str | Path | None = None,
) -> ContractOverlaySummary:
    loaded_players = load_roster_csv(roster_csv)
    cleared_players = [player for player in loaded_players if has_contract_data(player)]
    players = [clear_contract_data(player) for player in loaded_players]
    contract_rows = read_contract_rows(contracts_csv)
    players_by_source_id: dict[str, list[int]] = {}
    players_by_team_name: dict[tuple[str, str], list[int]] = {}
    players_by_name: dict[str, list[int]] = {}
    for index, player in enumerate(players):
        if source_identity(player):
            players_by_source_id.setdefault(source_identity(player), []).append(index)
        players_by_team_name.setdefault(
            (player.team_id, compact_name(player.player_name)), []
        ).append(index)
        players_by_name.setdefault(compact_name(player.player_name), []).append(index)

    matched_indexes: set[int] = set()
    audit_rows: list[dict[str, str]] = []
    unmatched = 0
    ambiguous = 0
    for player in cleared_players:
        audit_rows.append(cleared_contract_audit_row(player))
    for row in contract_rows:
        indexes = contract_match_indexes(
            row, players_by_source_id, players_by_team_name, players_by_name
        )
        if len(indexes) != 1:
            status = "ambiguous" if indexes else "unmatched"
            ambiguous += status == "ambiguous"
            unmatched += status == "unmatched"
            audit_rows.append(contract_audit_row(row, status, ""))
            continue
        index = indexes[0]
        if index in matched_indexes:
            ambiguous += 1
            audit_rows.append(contract_audit_row(row, "duplicate_target", players[index].player_name))
            continue
        if not contract_snapshot_matches(players[index], row):
            unmatched += 1
            audit_rows.append(
                contract_audit_row(row, "snapshot_mismatch", players[index].player_name)
            )
            continue
        players[index] = apply_contract(players[index], row)
        matched_indexes.add(index)
        audit_rows.append(contract_audit_row(row, "matched", players[index].player_name))

    eligible_indexes = {
        index for index, player in enumerate(players) if player.league_level == "NHL"
    }
    for index in sorted(eligible_indexes - matched_indexes):
        audit_rows.append(missing_contract_audit_row(players[index]))

    write_roster_csv(output_csv, players)
    if audit_csv is not None:
        write_audit_csv(audit_csv, audit_rows)
    return ContractOverlaySummary(
        roster_players=len(players),
        eligible_nhl_players=len(eligible_indexes),
        contract_rows=len(contract_rows),
        matched_players=len(matched_indexes),
        matched_nhl_players=len(matched_indexes & eligible_indexes),
        unmatched_contracts=unmatched,
        ambiguous_contracts=ambiguous,
    )


def normalize_contract_export(
    input_csv: str | Path,
    output_csv: str | Path,
    *,
    snapshot_date: str,
    metadata_json: str | Path,
    audit_csv: str | Path | None = None,
) -> ContractNormalizationSummary:
    """Normalize a permitted cached export and reject rows unsafe for historical use."""
    snapshot = parse_iso_date(snapshot_date)
    metadata = read_source_metadata(metadata_json, input_csv=input_csv, expected_snapshot=snapshot)
    with Path(input_csv).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = resolve_raw_columns(reader.fieldnames or [])
        raw_rows = list(reader)

    required = {"team_id", "player_name", "cap_hit", "contract_end_year"}
    missing = required - set(columns)
    if missing:
        raise ValueError(f"raw contract CSV missing mapped columns: {', '.join(sorted(missing))}")

    candidates: list[tuple[int, dict[str, str]]] = []
    audit_rows: list[dict[str, str]] = []
    future_signings = 0
    for row_number, raw in enumerate(raw_rows, start=2):
        try:
            normalized, reason = normalize_raw_contract_row(
                raw,
                columns,
                snapshot=snapshot,
                source=metadata.source,
                source_url=metadata.source_url,
            )
        except ValueError:
            normalized, reason = {}, "malformed_value"
        if reason:
            future_signings += reason == "future_signing"
            audit_rows.append(normalization_audit_row(row_number, raw, columns, "rejected", reason))
        else:
            candidates.append((row_number, normalized))

    accepted: list[dict[str, str]] = []
    conflicts = 0
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, str]]]] = {}
    for item in candidates:
        key = (item[1]["team_id"], compact_name(item[1]["player_name"]))
        grouped.setdefault(key, []).append(item)
    for items in grouped.values():
        ids = {row["player_id"] for _, row in items if row["player_id"]}
        signatures = {
            (
                row["cap_hit"],
                row["contract_end_year"],
                row["contract_years_remaining"],
                row["contract_type"],
                row["trade_protection"],
            )
            for _, row in items
        }
        if len(ids) > 1 or len(signatures) > 1:
            conflicts += len(items)
            for row_number, row in items:
                audit_rows.append(
                    normalization_audit_row(
                        row_number, row, {}, "rejected", "conflicting_duplicate"
                    )
                )
            continue
        items.sort(key=lambda item: bool(item[1]["player_id"]), reverse=True)
        accepted.append(items[0][1])
        audit_rows.append(
            normalization_audit_row(items[0][0], items[0][1], {}, "normalized", "")
        )
        for row_number, row in items[1:]:
            audit_rows.append(normalization_audit_row(row_number, row, {}, "rejected", "duplicate"))

    accepted.sort(key=lambda row: (row["team_id"], row["player_name"]))
    write_contract_csv(output_csv, accepted)
    if audit_csv is not None:
        write_normalization_audit_csv(audit_csv, audit_rows)
    rejected = len(raw_rows) - len(accepted)
    return ContractNormalizationSummary(
        input_rows=len(raw_rows),
        normalized_rows=len(accepted),
        rejected_rows=rejected,
        future_signing_rows=future_signings,
        conflicting_duplicate_rows=conflicts,
    )


def resolve_raw_columns(fieldnames: list[str]) -> dict[str, str]:
    available = {normalize_column_name(name): name for name in fieldnames}
    resolved = {}
    for canonical, aliases in RAW_COLUMN_ALIASES.items():
        for alias in aliases:
            if normalize_column_name(alias) in available:
                resolved[canonical] = available[normalize_column_name(alias)]
                break
    return resolved


def normalize_raw_contract_row(
    raw: dict[str, str],
    columns: dict[str, str],
    *,
    snapshot: date,
    source: str,
    source_url: str,
) -> tuple[dict[str, str], str]:
    def value(key: str) -> str:
        return (raw.get(columns.get(key, ""), "") or "").strip()

    team_id = normalize_team_id(value("team_id"))
    player_name = value("player_name")
    cap_hit = parse_money(value("cap_hit"))
    end_year = to_int(value("contract_end_year"))
    signed_date = parse_optional_date(value("signed_date"))
    if not team_id:
        return {}, "invalid_team"
    if not player_name:
        return {}, "missing_player_name"
    if cap_hit < MIN_PLAUSIBLE_CAP_HIT or cap_hit > MAX_PLAUSIBLE_CAP_HIT:
        return {}, "implausible_cap_hit"
    if not end_year:
        return {}, "missing_contract_end_year"
    if end_year < snapshot.year:
        return {}, "expired_before_snapshot"
    if signed_date and signed_date > snapshot:
        return {}, "future_signing"
    years_remaining = to_float(value("contract_years_remaining")) or max(
        0.0, float(end_year - snapshot.year)
    )
    return {
        "team_id": team_id,
        "player_id": normalize_player_id(value("player_id")),
        "player_name": player_name,
        "cap_hit": str(cap_hit),
        "contract_end_year": str(end_year),
        "contract_years_remaining": f"{years_remaining:.1f}",
        "contract_type": value("contract_type"),
        "trade_protection": value("trade_protection"),
        "snapshot_date": snapshot.isoformat(),
        "source": source,
        "source_url": source_url,
    }, ""


def read_contract_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = CONTRACT_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"contract CSV missing required columns: {', '.join(sorted(missing))}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def read_source_metadata(
    path: str | Path,
    *,
    input_csv: str | Path,
    expected_snapshot: date,
) -> ContractSourceMetadata:
    metadata_path = Path(path)
    values = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("contract source metadata must be a JSON object")
    missing = SOURCE_METADATA_REQUIRED_FIELDS - set(values)
    if missing:
        raise ValueError(f"contract source metadata missing fields: {', '.join(sorted(missing))}")
    wrong_types = sorted(
        field for field in SOURCE_METADATA_REQUIRED_FIELDS if not isinstance(values[field], str)
    )
    if wrong_types:
        raise ValueError(
            "contract source metadata fields must be strings: " + ", ".join(wrong_types)
        )
    if values["snapshot_date"] != expected_snapshot.isoformat():
        raise ValueError("contract source metadata snapshot does not match requested snapshot")
    parse_iso_date(values["retrieved_at"])
    actual_hash = file_sha256(input_csv)
    if values["input_sha256"].lower() != actual_hash:
        raise ValueError("contract source metadata checksum does not match input CSV")
    if not str(values["access_basis"]).strip():
        raise ValueError("contract source metadata must document the access basis")
    if not str(values["source"]).strip():
        raise ValueError("contract source metadata must identify the source")
    if not str(values["source_url"]).strip():
        raise ValueError("contract source metadata must include the source URL")
    return ContractSourceMetadata(
        source=str(values["source"]).strip(),
        source_url=str(values["source_url"]).strip(),
        snapshot_date=str(values["snapshot_date"]),
        retrieved_at=str(values["retrieved_at"]),
        access_basis=str(values["access_basis"]).strip(),
        input_sha256=str(values["input_sha256"]).lower(),
    )


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contract_match_indexes(
    row: dict[str, str],
    players_by_source_id: dict[str, list[int]],
    players_by_team_name: dict[tuple[str, str], list[int]],
    players_by_name: dict[str, list[int]],
) -> list[int]:
    name = compact_name(row.get("player_name", ""))
    team_id = row.get("team_id", "").upper()
    source_id = normalize_player_id(row.get("player_id", ""))
    if source_id:
        if source_id not in players_by_source_id:
            return []
        team_name_indexes = set(players_by_team_name.get((team_id, name), []))
        return [index for index in players_by_source_id[source_id] if index in team_name_indexes]
    if team_id:
        return players_by_team_name.get((team_id, name), [])
    return players_by_name.get(name, [])


def contract_snapshot_matches(player: RosterPlayer, row: dict[str, str]) -> bool:
    if not player.snapshot_date:
        return False
    return row.get("snapshot_date", "") == player.snapshot_date


def apply_contract(player: RosterPlayer, row: dict[str, str]) -> RosterPlayer:
    end_year = to_int(row.get("contract_end_year", ""))
    years_remaining = to_float(row.get("contract_years_remaining", ""))
    snapshot_date = row.get("snapshot_date", "") or player.snapshot_date
    if not years_remaining and end_year and snapshot_date[:4].isdigit():
        years_remaining = max(0.0, float(end_year - int(snapshot_date[:4])))
    protection_type, restriction_share = normalize_trade_protection(row.get("trade_protection", ""))
    return replace(
        player,
        cap_hit=to_int(row.get("cap_hit", "")),
        contract_end_year=end_year,
        contract_years_remaining=years_remaining,
        contract_type=row.get("contract_type", ""),
        trade_protection=row.get("trade_protection", ""),
        trade_protection_type=protection_type,
        trade_restriction_share=restriction_share,
        contract_snapshot_date=snapshot_date,
        contract_source=row.get("source", ""),
        contract_source_url=row.get("source_url", ""),
    )


def has_contract_data(player: RosterPlayer) -> bool:
    return bool(
        player.cap_hit
        or player.contract_end_year
        or player.contract_years_remaining
        or player.contract_type
        or player.trade_protection
        or player.contract_snapshot_date
        or player.contract_source
    )


def clear_contract_data(player: RosterPlayer) -> RosterPlayer:
    return replace(
        player,
        cap_hit=0,
        contract_end_year=0,
        contract_years_remaining=0.0,
        contract_type="",
        trade_protection="",
        trade_protection_type="",
        trade_restriction_share=0.0,
        contract_snapshot_date="",
        contract_source="",
        contract_source_url="",
    )


def normalize_trade_protection(value: str, *, league_teams: int = 32) -> tuple[str, float]:
    """Classify mobility clauses and estimate the share of teams blocked."""
    normalized = value.strip().upper()
    if normalized in {"", "NONE", "NO", "N/A", "NA"}:
        return "none", 0.0
    if "NMC" in normalized or "NO-MOVE" in normalized or "NO MOVE" in normalized:
        return "no_move", 1.0
    modified = "M-NTC" in normalized or "MODIFIED" in normalized or "TEAM" in normalized
    team_count = first_team_count(normalized)
    if modified:
        if team_count:
            if "TRADE LIST" in normalized and "NO-TRADE" not in normalized and "NO TRADE" not in normalized:
                blocked_share = (league_teams - team_count) / league_teams
            else:
                blocked_share = team_count / league_teams
            return "modified_no_trade", min(1.0, max(0.0, blocked_share))
        return "modified_no_trade", 0.50
    if "NTC" in normalized or "NO-TRADE" in normalized or "NO TRADE" in normalized:
        return "no_trade", 1.0
    return "other", 0.25


def first_team_count(value: str) -> int:
    match = re.search(r"\b(\d{1,2})[- ]TEAM\b", value)
    return int(match.group(1)) if match else 0


def source_identity(player: RosterPlayer) -> str:
    return normalize_player_id(player.source_id or player.player_id)


def normalize_player_id(value: str) -> str:
    normalized = value.strip().lower()
    for prefix in ("nhl-", "puckpedia-", "capwages-"):
        normalized = normalized.removeprefix(prefix)
    return normalized


def compact_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if character.isascii() and character.isalnum())


def to_int(value: str) -> int:
    cleaned = value.replace("$", "").replace(",", "").strip()
    return int(float(cleaned)) if cleaned else 0


def to_float(value: str) -> float:
    cleaned = value.strip()
    return float(cleaned) if cleaned else 0.0


def parse_money(value: str) -> int:
    cleaned = value.replace("$", "").replace(",", "").strip().upper()
    if not cleaned or cleaned in {"-", "N/A", "NA"}:
        return 0
    multiplier = 1
    if cleaned.endswith("M"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith("K"):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    try:
        return int(float(cleaned) * multiplier)
    except ValueError:
        return 0


def normalize_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def normalize_team_id(value: str) -> str:
    compact = re.sub(r"[^A-Z0-9]+", "", value.upper())
    if compact in NHL_TEAM_IDS:
        return compact
    return TEAM_ALIASES.get(compact, "")


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"snapshot date must use YYYY-MM-DD: {value}") from error


def parse_optional_date(value: str) -> date | None:
    if not value:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"signed date must use YYYY-MM-DD or MM/DD/YYYY: {value}")


def write_contract_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NORMALIZED_CONTRACT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def contract_audit_row(row: dict[str, str], status: str, matched_player_name: str) -> dict[str, str]:
    return {
        "status": status,
        "team_id": row.get("team_id", ""),
        "player_id": row.get("player_id", ""),
        "player_name": row.get("player_name", ""),
        "matched_player_name": matched_player_name,
        "source": row.get("source", ""),
        "source_url": row.get("source_url", ""),
    }


def missing_contract_audit_row(player: RosterPlayer) -> dict[str, str]:
    return {
        "status": "missing_contract",
        "team_id": player.team_id,
        "player_id": source_identity(player),
        "player_name": player.player_name,
        "matched_player_name": "",
        "source": "",
        "source_url": "",
    }


def cleared_contract_audit_row(player: RosterPlayer) -> dict[str, str]:
    return {
        "status": "cleared_existing_contract",
        "team_id": player.team_id,
        "player_id": source_identity(player),
        "player_name": player.player_name,
        "matched_player_name": "",
        "source": player.contract_source,
        "source_url": player.contract_source_url,
    }


def normalization_audit_row(
    row_number: int,
    row: dict[str, str],
    columns: dict[str, str],
    status: str,
    reason: str,
) -> dict[str, str]:
    def value(key: str) -> str:
        return (row.get(columns.get(key, key), "") or "").strip()

    return {
        "row_number": str(row_number),
        "status": status,
        "reason": reason,
        "team_id": value("team_id"),
        "player_name": value("player_name"),
        "cap_hit": value("cap_hit"),
        "contract_end_year": value("contract_end_year"),
        "signed_date": value("signed_date"),
    }


def write_normalization_audit_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "row_number",
        "status",
        "reason",
        "team_id",
        "player_name",
        "cap_hit",
        "contract_end_year",
        "signed_date",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_audit_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["status", "team_id", "player_id", "player_name", "matched_player_name", "source", "source_url"]
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
