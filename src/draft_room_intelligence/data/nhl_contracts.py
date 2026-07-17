"""Overlay cached NHL contract and cap evidence onto normalized roster rows."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, replace
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


@dataclass(frozen=True)
class ContractOverlaySummary:
    roster_players: int
    contract_rows: int
    matched_players: int
    unmatched_contracts: int
    ambiguous_contracts: int


def enrich_roster_contracts(
    roster_csv: str | Path,
    contracts_csv: str | Path,
    output_csv: str | Path,
    *,
    audit_csv: str | Path | None = None,
) -> ContractOverlaySummary:
    players = load_roster_csv(roster_csv)
    contract_rows = read_contract_rows(contracts_csv)
    players_by_source_id: dict[str, list[int]] = {}
    players_by_team_name: dict[tuple[str, str], list[int]] = {}
    players_by_name: dict[str, list[int]] = {}
    for index, player in enumerate(players):
        if source_identity(player):
            players_by_source_id.setdefault(source_identity(player), []).append(index)
        players_by_team_name.setdefault((player.team_id, compact_name(player.player_name)), []).append(index)
        players_by_name.setdefault(compact_name(player.player_name), []).append(index)

    matched_indexes: set[int] = set()
    audit_rows: list[dict[str, str]] = []
    unmatched = 0
    ambiguous = 0
    for row in contract_rows:
        indexes = contract_match_indexes(row, players_by_source_id, players_by_team_name, players_by_name)
        if len(indexes) != 1:
            status = "ambiguous" if indexes else "unmatched"
            ambiguous += status == "ambiguous"
            unmatched += status == "unmatched"
            audit_rows.append(contract_audit_row(row, status, ""))
            continue
        index = indexes[0]
        if not contract_snapshot_matches(players[index], row):
            unmatched += 1
            audit_rows.append(contract_audit_row(row, "snapshot_mismatch", players[index].player_name))
            continue
        players[index] = apply_contract(players[index], row)
        matched_indexes.add(index)
        audit_rows.append(contract_audit_row(row, "matched", players[index].player_name))

    write_roster_csv(output_csv, players)
    if audit_csv is not None:
        write_audit_csv(audit_csv, audit_rows)
    return ContractOverlaySummary(
        roster_players=len(players),
        contract_rows=len(contract_rows),
        matched_players=len(matched_indexes),
        unmatched_contracts=unmatched,
        ambiguous_contracts=ambiguous,
    )


def read_contract_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = CONTRACT_REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"contract CSV missing required columns: {', '.join(sorted(missing))}")
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def contract_match_indexes(
    row: dict[str, str],
    players_by_source_id: dict[str, list[int]],
    players_by_team_name: dict[tuple[str, str], list[int]],
    players_by_name: dict[str, list[int]],
) -> list[int]:
    name = compact_name(row.get("player_name", ""))
    team_id = row.get("team_id", "").upper()
    source_id = normalize_player_id(row.get("player_id", ""))
    if source_id and source_id in players_by_source_id:
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
        contract_source=row.get("source", ""),
        contract_source_url=row.get("source_url", ""),
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


def write_audit_csv(path: str | Path, rows: list[dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["status", "team_id", "player_id", "player_name", "matched_player_name", "source", "source_url"]
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
