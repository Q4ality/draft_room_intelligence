"""Report outcome-label staging readiness across configured draft classes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from draft_room_intelligence.data.draft_range_etl import DraftClassETLSpec
from draft_room_intelligence.reports.longitudinal_outcomes import (
    REQUIRED_COLUMNS,
    SUPPORTED_HORIZONS,
    load_outcome_labels,
)


@dataclass(frozen=True)
class OutcomeLabelCoverageReport:
    as_of_date: date
    rows: list[dict[str, str]]


def build_outcome_label_coverage_report(
    specs: Iterable[DraftClassETLSpec],
    *,
    as_of_date: date,
    start_year: int = 2014,
    end_year: int = 2021,
    horizons: tuple[int, ...] = SUPPORTED_HORIZONS,
    labels_root: str | Path | None = None,
) -> OutcomeLabelCoverageReport:
    rows: list[dict[str, str]] = []
    for spec in specs:
        if not spec.enabled or not start_year <= spec.draft_year <= end_year:
            continue
        snapshot = resolve_snapshot_dir(spec)
        players_path = snapshot / "players.csv"
        players = read_csv(players_path) if players_path.is_file() else []
        for horizon_years in horizons:
            outcomes_path = (
                Path(labels_root) / str(spec.draft_year) / f"{horizon_years}y.csv"
                if labels_root
                else snapshot / "nhl_outcomes.csv"
            )
            outcomes = read_csv(outcomes_path) if outcomes_path.is_file() else []
            outcome_columns = set(outcomes[0]) if outcomes else csv_columns(outcomes_path)
            required_through = date(spec.draft_year + horizon_years, 6, 30)
            status, detail = coverage_status(
                required_through=required_through,
                as_of_date=as_of_date,
                players_path=players_path,
                outcomes_path=outcomes_path,
                player_ids={row.get("player_id", "").strip() for row in players},
                draft_year=spec.draft_year,
                horizon_years=horizon_years,
                outcome_rows=outcomes,
                outcome_columns=outcome_columns,
            )
            rows.append(
                {
                    "draft_year": str(spec.draft_year),
                    "horizon_years": str(horizon_years),
                    "required_through": required_through.isoformat(),
                    "snapshot_dir": str(snapshot),
                    "player_count": str(len(players)),
                    "outcome_row_count": str(len(outcomes)),
                    "status": status,
                    "detail": detail,
                }
            )
    return OutcomeLabelCoverageReport(as_of_date=as_of_date, rows=rows)


def write_outcome_label_coverage_report(
    specs: Iterable[DraftClassETLSpec],
    output_dir: str | Path,
    *,
    as_of_date: date,
    start_year: int = 2014,
    end_year: int = 2021,
    labels_root: str | Path | None = None,
) -> OutcomeLabelCoverageReport:
    report = build_outcome_label_coverage_report(
        specs,
        as_of_date=as_of_date,
        start_year=start_year,
        end_year=end_year,
        labels_root=labels_root,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "draft_year",
        "horizon_years",
        "required_through",
        "snapshot_dir",
        "player_count",
        "outcome_row_count",
        "status",
        "detail",
    ]
    with (root / "coverage.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report.rows)
    (root / "summary.md").write_text(format_outcome_label_coverage(report), encoding="utf-8")
    return report


def resolve_snapshot_dir(spec: DraftClassETLSpec) -> Path:
    final_dir = spec.output_dir / "final"
    if final_dir.is_dir():
        return final_dir
    return spec.base_dir or final_dir


def coverage_status(
    *,
    required_through: date,
    as_of_date: date,
    players_path: Path,
    outcomes_path: Path,
    player_ids: set[str],
    draft_year: int,
    horizon_years: int,
    outcome_rows: list[dict[str, str]],
    outcome_columns: set[str],
) -> tuple[str, str]:
    if required_through > as_of_date:
        return "not_mature_yet", "declared horizon ends after the audit date"
    if not players_path.is_file():
        return "missing_normalized_class", "players.csv is not available in the configured snapshot"
    if not outcomes_path.is_file() or not outcome_rows:
        return "needs_time_bounded_export", "no cached NHL outcome export is available"
    missing = sorted(set(REQUIRED_COLUMNS) - outcome_columns)
    if missing:
        return (
            "requires_time_bounded_export",
            "existing outcome rows lack canonical label fields: " + ", ".join(missing),
        )
    try:
        labels = load_outcome_labels(outcomes_path, as_of_date=as_of_date)
    except ValueError as error:
        return "invalid_canonical_labels", str(error)
    class_labels = [
        label
        for label in labels
        if label.draft_year == draft_year and label.horizon_years == horizon_years
    ]
    if not class_labels:
        return "incomplete_canonical_labels", "no labels match this class and horizon"
    if any(not label.is_mature for label in class_labels):
        return "immature_canonical_labels", "one or more labels end before the required horizon"
    label_ids = {label.player_id for label in class_labels}
    if label_ids != player_ids:
        missing_ids = len(player_ids - label_ids)
        unknown_ids = len(label_ids - player_ids)
        return (
            "incomplete_canonical_labels",
            f"player coverage mismatch: missing={missing_ids}, unknown={unknown_ids}",
        )
    return "ready_for_label_audit", "canonical time-bounded outcome rows are present"


def format_outcome_label_coverage(report: OutcomeLabelCoverageReport) -> str:
    counts: dict[str, int] = {}
    for row in report.rows:
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1
    lines = [
        "# Longitudinal Outcome Label Coverage",
        "",
        f"- Audit date: {report.as_of_date.isoformat()}",
        f"- Class-horizon rows: {len(report.rows)}",
        "- Status counts: "
        + ", ".join(f"{status}={count}" for status, count in sorted(counts.items())),
        "",
        "Rows marked `requires_time_bounded_export` must not be used as retrospective labels. "
        "A current or career-total snapshot does not establish a historical cutoff.",
        "",
        "| Draft | Horizon | Required through | Players | Outcome rows | Status |",
        "| ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            f"| {row['draft_year']} | {row['horizon_years']} | {row['required_through']} | "
            f"{row['player_count']} | {row['outcome_row_count']} | {row['status']} |"
        )
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def csv_columns(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return set(csv.DictReader(handle).fieldnames or [])
