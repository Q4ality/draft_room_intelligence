"""Overlay Elite Prospects PDF guide tables onto a demo dataset."""

from __future__ import annotations

import csv
import shutil
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from draft_room_intelligence.data.eliteprospects_csv import PLAYER_COLUMNS
from draft_room_intelligence.data.eliteprospects_csv import SEASON_STAT_LINE_COLUMNS
from draft_room_intelligence.data.eliteprospects_csv import write_table
from draft_room_intelligence.data.eliteprospects_pdf import EP_PDF_PROFILE_COLUMNS
from draft_room_intelligence.data.eliteprospects_pdf import EP_PDF_TOOL_GRADE_COLUMNS
from draft_room_intelligence.data.eliteprospects_pdf import RANKING_COLUMNS
from draft_room_intelligence.data.normalized_merge import read_optional_table
from draft_room_intelligence.data.normalized_merge import read_table
from draft_room_intelligence.data.stat_reconciliation import RECONCILIATION_AUDIT_COLUMNS
from draft_room_intelligence.data.stat_reconciliation import StatReconciliationResult
from draft_room_intelligence.data.stat_reconciliation import reconcile_stat_lines


AUDIT_COLUMNS = [
    "source_player_id",
    "source_name",
    "base_player_id",
    "base_name",
    "match_method",
    "match_score",
]


@dataclass(frozen=True)
class EpPdfOverlaySummary:
    base_players: int
    source_players: int
    matched_players: int
    exact_matches: int
    alias_matches: int
    fuzzy_matches: int
    unmatched_source_players: int
    base_stat_lines: int
    added_stat_lines: int
    augmented_stat_lines: int
    output_stat_lines: int
    reconciled_duplicate_groups: int
    reconciliation_conflict_groups: int
    profile_rows: int
    tool_grade_rows: int


def overlay_ep_pdf_demo_dataset(
    base_dir: str | Path,
    ep_pdf_dir: str | Path,
    output_dir: str | Path,
    *,
    fuzzy_threshold: float = 0.9,
) -> EpPdfOverlaySummary:
    base_root = Path(base_dir)
    source_root = Path(ep_pdf_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    base_players = read_table(base_root / "players.csv")
    source_players = read_table(source_root / "players.csv")
    base_stats = read_optional_table(base_root / "season_stat_lines.csv")
    source_stats = read_optional_table(source_root / "season_stat_lines.csv")
    source_rankings = read_optional_table(source_root / "rankings.csv")
    source_profiles = read_optional_table(source_root / "ep_pdf_profiles.csv")
    source_tool_grades = read_optional_table(source_root / "ep_pdf_tool_grades.csv")

    matches, audit_rows = match_source_players(source_players, base_players, fuzzy_threshold=fuzzy_threshold)
    merged_players = merge_players(base_players, source_players, matches)
    merged_stats, added_stat_lines, augmented_stat_lines, reconciliation = merge_stat_lines(
        base_stats,
        source_stats,
        matches,
    )
    remapped_rankings = remap_rows(source_rankings, matches)
    remapped_profiles = remap_rows(source_profiles, matches)
    remapped_tool_grades = remap_rows(source_tool_grades, matches)

    write_table(output_root / "players.csv", PLAYER_COLUMNS, merged_players)
    write_table(output_root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, merged_stats)
    write_table(
        output_root / "stat_line_reconciliation_audit.csv",
        RECONCILIATION_AUDIT_COLUMNS,
        reconciliation.audit_rows,
    )
    write_table(
        output_root / "rankings.csv",
        RANKING_COLUMNS,
        [*read_optional_table(base_root / "rankings.csv"), *remapped_rankings],
    )
    write_table(
        output_root / "ep_pdf_profiles.csv",
        EP_PDF_PROFILE_COLUMNS,
        remapped_profiles,
    )
    write_table(
        output_root / "ep_pdf_tool_grades.csv",
        EP_PDF_TOOL_GRADE_COLUMNS,
        remapped_tool_grades,
    )
    write_table(output_root / "ep_pdf_match_audit.csv", AUDIT_COLUMNS, audit_rows)
    copy_passthrough(base_root, output_root)

    return EpPdfOverlaySummary(
        base_players=len(base_players),
        source_players=len(source_players),
        matched_players=len(matches),
        exact_matches=count_method(audit_rows, "exact"),
        alias_matches=count_method(audit_rows, "alias"),
        fuzzy_matches=count_method(audit_rows, "fuzzy"),
        unmatched_source_players=len(source_players) - len(matches),
        base_stat_lines=len(base_stats),
        added_stat_lines=added_stat_lines,
        augmented_stat_lines=augmented_stat_lines,
        output_stat_lines=len(merged_stats),
        reconciled_duplicate_groups=reconciliation.duplicate_groups,
        reconciliation_conflict_groups=reconciliation.conflict_groups,
        profile_rows=len(remapped_profiles),
        tool_grade_rows=len(remapped_tool_grades),
    )


def match_source_players(
    source_players: list[dict[str, str]],
    base_players: list[dict[str, str]],
    *,
    fuzzy_threshold: float,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    exact_index = unique_index(base_players, normalized_name_key)
    alias_index = unique_index(base_players, alias_name_key)
    used_base_ids: set[str] = set()
    matches: dict[str, str] = {}
    audit_rows: list[dict[str, str]] = []

    for source_player in source_players:
        source_id = source_player["player_id"]
        source_name = source_player["name"]
        base_player = exact_index.get(normalized_name_key(source_name))
        method = "exact"
        score = 1.0
        if base_player is None:
            base_player = alias_index.get(alias_name_key(source_name))
            method = "alias"
        if base_player is None:
            base_player, score = best_fuzzy_match(source_name, base_players)
            method = "fuzzy"
            if score < fuzzy_threshold:
                continue
        if base_player["player_id"] in used_base_ids:
            continue
        matches[source_id] = base_player["player_id"]
        used_base_ids.add(base_player["player_id"])
        audit_rows.append(
            {
                "source_player_id": source_id,
                "source_name": source_name,
                "base_player_id": base_player["player_id"],
                "base_name": base_player["name"],
                "match_method": method,
                "match_score": f"{score:.3f}",
            }
        )
    return matches, audit_rows


def unique_index(
    rows: list[dict[str, str]],
    key_fn,
) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        key = key_fn(row["name"])
        grouped.setdefault(key, []).append(row)
    return {key: values[0] for key, values in grouped.items() if len(values) == 1}


def best_fuzzy_match(
    source_name: str,
    base_players: list[dict[str, str]],
) -> tuple[dict[str, str] | None, float]:
    source_key = normalized_name_key(source_name)
    scored = [
        (base_player, SequenceMatcher(None, source_key, normalized_name_key(base_player["name"])).ratio())
        for base_player in base_players
    ]
    if not scored:
        return None, 0.0
    return max(scored, key=lambda item: item[1])


def merge_players(
    base_players: list[dict[str, str]],
    source_players: list[dict[str, str]],
    matches: dict[str, str],
) -> list[dict[str, str]]:
    source_by_base_id = {
        matches[source_player["player_id"]]: source_player
        for source_player in source_players
        if source_player["player_id"] in matches
    }
    merged: list[dict[str, str]] = []
    for base_player in base_players:
        row = dict(base_player)
        source_player = source_by_base_id.get(base_player["player_id"])
        if source_player:
            for column in ("birth_date", "position", "handedness", "height_cm", "weight_kg"):
                if source_player.get(column):
                    row[column] = source_player[column]
            row["source"] = append_source_label(row.get("source", ""), "eliteprospects_pdf")
            row["source_id"] = source_player.get("source_id", row.get("source_id", ""))
            row["source_url"] = source_player.get("source_url", row.get("source_url", ""))
        merged.append(row)
    return merged


def merge_stat_lines(
    base_stats: list[dict[str, str]],
    source_stats: list[dict[str, str]],
    matches: dict[str, str],
) -> tuple[list[dict[str, str]], int, int, StatReconciliationResult]:
    candidate_rows = [dict(row) for row in base_stats]
    candidate_count = 0
    for source_row in source_stats:
        base_id = matches.get(source_row["player_id"])
        if not base_id:
            continue
        row = normalize_columns(dict(source_row), SEASON_STAT_LINE_COLUMNS)
        row["player_id"] = base_id
        candidate_rows.append(row)
        candidate_count += 1
    reconciliation = reconcile_stat_lines(candidate_rows)
    added = max(0, len(reconciliation.rows) - len(base_stats))
    augmented = max(0, candidate_count - added)
    return reconciliation.rows, added, augmented, reconciliation


def remap_rows(rows: list[dict[str, str]], matches: dict[str, str]) -> list[dict[str, str]]:
    remapped: list[dict[str, str]] = []
    for row in rows:
        base_id = matches.get(row.get("player_id", ""))
        if not base_id:
            continue
        updated = dict(row)
        updated["player_id"] = base_id
        remapped.append(updated)
    return remapped


def copy_passthrough(base_root: Path, output_root: Path) -> None:
    for filename in ("draft_selections.csv", "nhl_outcomes.csv"):
        source = base_root / filename
        if source.exists():
            shutil.copyfile(source, output_root / filename)
    for path in base_root.glob("*_matches.csv"):
        shutil.copyfile(path, output_root / path.name)


def normalized_name_key(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(character.lower() for character in ascii_value if character.isalnum())


def alias_name_key(value: str) -> str:
    parts = normalized_words(value)
    if len(parts) < 2:
        return normalized_name_key(value)
    return f"{parts[0][:1]}{parts[-1]}"


def normalized_words(value: str) -> list[str]:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ["".join(character.lower() for character in part if character.isalnum()) for part in ascii_value.split()]


def append_source_label(existing: str, label: str) -> str:
    labels = [item.strip() for item in existing.split(";") if item.strip()]
    if label not in labels:
        labels.append(label)
    return "; ".join(labels)


def normalize_columns(row: dict[str, str], columns: list[str]) -> dict[str, str]:
    return {column: row.get(column, "") for column in columns}


def count_method(rows: list[dict[str, str]], method: str) -> int:
    return sum(1 for row in rows if row.get("match_method") == method)


def write_overlay_report(path: str | Path, summary: EpPdfOverlaySummary) -> None:
    lines = [
        "# Elite Prospects PDF Demo Overlay",
        "",
        "## Summary",
        f"- base_players: {summary.base_players}",
        f"- source_players: {summary.source_players}",
        f"- matched_players: {summary.matched_players}",
        f"- exact_matches: {summary.exact_matches}",
        f"- alias_matches: {summary.alias_matches}",
        f"- fuzzy_matches: {summary.fuzzy_matches}",
        f"- unmatched_source_players: {summary.unmatched_source_players}",
        f"- base_stat_lines: {summary.base_stat_lines}",
        f"- added_stat_lines: {summary.added_stat_lines}",
        f"- augmented_stat_lines: {summary.augmented_stat_lines}",
        f"- output_stat_lines: {summary.output_stat_lines}",
        f"- reconciled_duplicate_groups: {summary.reconciled_duplicate_groups}",
        f"- reconciliation_conflict_groups: {summary.reconciliation_conflict_groups}",
        f"- profile_rows: {summary.profile_rows}",
        f"- tool_grade_rows: {summary.tool_grade_rows}",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
