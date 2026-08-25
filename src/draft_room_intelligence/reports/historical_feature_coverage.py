"""Audit pre-draft consensus and production feature coverage by draft class."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HistoricalFeatureCoverageReport:
    rows: list[dict[str, str]]


def build_historical_feature_coverage_report(
    class_root: str | Path,
    *,
    start_year: int = 2014,
    end_year: int = 2021,
) -> HistoricalFeatureCoverageReport:
    root = Path(class_root)
    rows = [
        coverage_row(root / str(year) / "final", year) for year in range(start_year, end_year + 1)
    ]
    return HistoricalFeatureCoverageReport(rows=rows)


def coverage_row(snapshot: Path, draft_year: int) -> dict[str, str]:
    players = read_csv(snapshot / "players.csv")
    rankings = read_csv(snapshot / "rankings.csv")
    stat_lines = read_csv(snapshot / "season_stat_lines.csv")
    advanced_lines = read_csv(snapshot / "advanced_stat_lines.csv")
    player_ids = {row.get("player_id", "").strip() for row in players} - {""}
    consensus_ids = {
        row.get("player_id", "").strip()
        for row in rankings
        if row.get("player_id", "").strip()
        and row.get("rank", "").strip()
        and row.get("source", "").strip() != "draft_slot_proxy"
    }
    proxy_ids = {
        row.get("player_id", "").strip()
        for row in rankings
        if row.get("player_id", "").strip() and row.get("source", "").strip() == "draft_slot_proxy"
    }
    production_ids = {row.get("player_id", "").strip() for row in stat_lines} - {""}
    advanced_ids = {row.get("player_id", "").strip() for row in advanced_lines} - {""}
    status, detail = readiness_status(
        player_ids,
        consensus_ids,
        production_ids,
        snapshot_exists=snapshot.is_dir(),
    )
    return {
        "draft_year": str(draft_year),
        "snapshot_dir": str(snapshot),
        "player_count": str(len(player_ids)),
        "ranking_row_count": str(len(rankings)),
        "consensus_player_count": str(len(consensus_ids & player_ids)),
        "draft_slot_proxy_player_count": str(len(proxy_ids & player_ids)),
        "production_player_count": str(len(production_ids & player_ids)),
        "advanced_player_count": str(len(advanced_ids & player_ids)),
        "status": status,
        "detail": detail,
    }


def readiness_status(
    player_ids: set[str],
    consensus_ids: set[str],
    production_ids: set[str],
    *,
    snapshot_exists: bool,
) -> tuple[str, str]:
    if not snapshot_exists or not player_ids:
        return "missing_normalized_class", "normalized player snapshot is unavailable"
    missing_consensus = len(player_ids - consensus_ids)
    missing_production = len(player_ids - production_ids)
    if not consensus_ids and not production_ids:
        return (
            "needs_consensus_and_production",
            "only draft-slot proxies or no rankings are present; pre-draft stat lines are absent",
        )
    if missing_consensus and missing_production:
        return (
            "partial_consensus_and_production",
            f"missing consensus={missing_consensus}, production={missing_production}",
        )
    if missing_consensus:
        return "needs_consensus", f"missing consensus for {missing_consensus} drafted players"
    if missing_production:
        return "needs_production", f"missing production for {missing_production} drafted players"
    return "ready_for_consensus_and_production", "complete pre-draft feature coverage"


def write_historical_feature_coverage_report(
    class_root: str | Path,
    output_dir: str | Path,
    *,
    start_year: int = 2014,
    end_year: int = 2021,
) -> HistoricalFeatureCoverageReport:
    report = build_historical_feature_coverage_report(
        class_root, start_year=start_year, end_year=end_year
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    fieldnames = list(report.rows[0]) if report.rows else ["draft_year"]
    with (root / "coverage.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report.rows)
    (root / "summary.md").write_text(format_historical_feature_coverage(report), encoding="utf-8")
    return report


def format_historical_feature_coverage(report: HistoricalFeatureCoverageReport) -> str:
    counts: dict[str, int] = {}
    for row in report.rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [
        "# Historical Pre-Draft Feature Coverage",
        "",
        f"- Draft classes: {len(report.rows)}",
        "- Status counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())),
        "",
        "`draft_slot_proxy` is not consensus and must not be used as a consensus feature. "
        "Production coverage counts only normalized pre-draft season stat lines.",
        "",
        "| Draft | Players | Consensus | Slot proxy | Production | Advanced | Status |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            f"| {row['draft_year']} | {row['player_count']} | {row['consensus_player_count']} | "
            f"{row['draft_slot_proxy_player_count']} | {row['production_player_count']} | "
            f"{row['advanced_player_count']} | {row['status']} |"
        )
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
