"""Quality reporting for merged normalized prospect datasets."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MergeQualityReport:
    base_players: int
    source_players: int
    merged_players: int
    matched_source_players: int
    unmatched_source_players: int
    matched_rate: float
    replaced_pre_draft_players: int
    base_pre_draft_players: int
    merged_pre_draft_players: int
    source_stat_lines_used: int
    duplicate_stat_lines: int
    missing_games: int
    missing_points: int
    base_league_counts: dict[str, int]
    merged_league_counts: dict[str, int]
    added_leagues: tuple[str, ...]
    removed_leagues: tuple[str, ...]


def build_merge_quality_report(
    base_dir: str | Path,
    source_dir: str | Path,
    merged_dir: str | Path,
    *,
    source_name: str = "eliteprospects",
    timing: str = "pre_draft",
) -> MergeQualityReport:
    base_root = Path(base_dir)
    source_root = Path(source_dir)
    merged_root = Path(merged_dir)

    base_players = read_table(base_root / "players.csv")
    source_players = read_table(source_root / "players.csv")
    merged_players = read_table(merged_root / "players.csv")
    base_stats = read_optional_table(base_root / "season_stat_lines.csv")
    merged_stats = read_optional_table(merged_root / "season_stat_lines.csv")
    unmatched = read_optional_table(merged_root / "unmatched_source_players.csv")

    source_ids = {row["source_id"] for row in source_players if row.get("source_id")}
    matched_source_ids = {
        row["source_id"]
        for row in merged_players
        if row.get("source") == source_name and row.get("source_id") in source_ids
    }
    merged_source_player_ids = {
        row["player_id"]
        for row in merged_players
        if row.get("source") == source_name and row.get("source_id") in source_ids
    }
    base_timing_player_ids = player_ids_with_timing(base_stats, timing)
    merged_timing_player_ids = player_ids_with_timing(merged_stats, timing)
    source_stat_lines_used = sum(1 for row in merged_stats if row.get("source") == source_name)

    base_leagues = league_counts(base_stats, timing)
    merged_leagues = league_counts(merged_stats, timing)

    return MergeQualityReport(
        base_players=len(base_players),
        source_players=len(source_players),
        merged_players=len(merged_players),
        matched_source_players=len(matched_source_ids),
        unmatched_source_players=len(unmatched),
        matched_rate=safe_rate(len(matched_source_ids), len(source_players)),
        replaced_pre_draft_players=len(merged_source_player_ids & base_timing_player_ids),
        base_pre_draft_players=len(base_timing_player_ids),
        merged_pre_draft_players=len(merged_timing_player_ids),
        source_stat_lines_used=source_stat_lines_used,
        duplicate_stat_lines=count_duplicate_stat_lines(merged_stats),
        missing_games=count_missing_numeric(merged_stats, "games"),
        missing_points=count_missing_numeric(merged_stats, "points"),
        base_league_counts=base_leagues,
        merged_league_counts=merged_leagues,
        added_leagues=tuple(sorted(set(merged_leagues) - set(base_leagues))),
        removed_leagues=tuple(sorted(set(base_leagues) - set(merged_leagues))),
    )


def format_merge_quality_report(report: MergeQualityReport) -> str:
    lines = [
        "# Merge Quality Report",
        "",
        "## Matching",
        f"- base_players: {report.base_players}",
        f"- source_players: {report.source_players}",
        f"- merged_players: {report.merged_players}",
        f"- matched_source_players: {report.matched_source_players}",
        f"- unmatched_source_players: {report.unmatched_source_players}",
        f"- matched_rate: {report.matched_rate:.3f}",
        "",
        "## Stat Lines",
        f"- replaced_pre_draft_players: {report.replaced_pre_draft_players}",
        f"- base_pre_draft_players: {report.base_pre_draft_players}",
        f"- merged_pre_draft_players: {report.merged_pre_draft_players}",
        f"- source_stat_lines_used: {report.source_stat_lines_used}",
        f"- duplicate_stat_lines: {report.duplicate_stat_lines}",
        f"- missing_games: {report.missing_games}",
        f"- missing_points: {report.missing_points}",
        "",
        "## League Coverage",
        f"- base_leagues: {len(report.base_league_counts)}",
        f"- merged_leagues: {len(report.merged_league_counts)}",
        f"- added_leagues: {', '.join(report.added_leagues) or 'none'}",
        f"- removed_leagues: {', '.join(report.removed_leagues) or 'none'}",
        "",
        "### Top Merged Leagues",
    ]
    for league, count in sorted(
        report.merged_league_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:10]:
        lines.append(f"- {league}: {count}")
    return "\n".join(lines)


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"missing required table: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def read_optional_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_table(path)


def player_ids_with_timing(rows: list[dict[str, str]], timing: str) -> set[str]:
    return {
        row["player_id"]
        for row in rows
        if row.get("player_id") and row.get("timing", "").strip() == timing
    }


def league_counts(rows: list[dict[str, str]], timing: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row.get("timing", "").strip() != timing:
            continue
        league = row.get("league", "").strip() or "Unknown"
        counts[league] += 1
    return dict(counts)


def count_duplicate_stat_lines(rows: list[dict[str, str]]) -> int:
    keys = [
        (
            row.get("player_id", ""),
            row.get("season", ""),
            row.get("league", ""),
            row.get("team", ""),
            row.get("timing", ""),
        )
        for row in rows
    ]
    counts = Counter(keys)
    return sum(count - 1 for count in counts.values() if count > 1)


def count_missing_numeric(rows: list[dict[str, str]], column: str) -> int:
    return sum(1 for row in rows if not row.get(column, "").strip())


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
