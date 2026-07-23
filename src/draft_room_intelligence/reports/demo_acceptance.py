"""Acceptance checks for business-demo readiness."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.reports.demo_baseline import (
    artifact_metrics,
    load_demo_baseline,
)

CHECK_COLUMNS = ["check_id", "status", "actual", "expected", "detail"]


@dataclass(frozen=True)
class AcceptanceCheck:
    check_id: str
    status: str
    actual: str
    expected: str
    detail: str

    def to_row(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "actual": self.actual,
            "expected": self.expected,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DemoAcceptanceReport:
    checks: list[AcceptanceCheck]

    @property
    def passed(self) -> bool:
        return all(check.status == "pass" for check in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.status != "pass")


def write_demo_acceptance_report(demo_output_dir: str | Path, output_dir: str | Path) -> DemoAcceptanceReport:
    report = build_demo_acceptance_report(demo_output_dir)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "acceptance_checks.csv", CHECK_COLUMNS, [check.to_row() for check in report.checks])
    (root / "summary.md").write_text(format_demo_acceptance_report(report), encoding="utf-8")
    return report


def build_demo_acceptance_report(demo_output_dir: str | Path) -> DemoAcceptanceReport:
    root = Path(demo_output_dir)
    board = read_csv(root / "board.csv")
    details = json.loads((root / "players.json").read_text(encoding="utf-8"))
    manifest = read_json(root / "manifest.json")
    baseline = load_demo_baseline(root)
    html = (root / "index.html").read_text(encoding="utf-8")
    brief_html = root / "meeting_brief.html"
    brief_pdf = root / "meeting_brief.pdf"
    board_by_name = {row["name"]: row for row in board}
    details_by_name = {str(detail.get("header", {}).get("name", "")): detail for detail in details}
    misa_sjs = team_fit_option(details_by_name.get("Michael Misa", {}), "SJS")
    schaefer_nyi = team_fit_option(details_by_name.get("Matthew Schaefer", {}), "NYI")
    schaefer_chi = team_fit_option(details_by_name.get("Matthew Schaefer", {}), "CHI")
    checks = baseline_acceptance_checks(baseline, manifest, board, details) + [
        threshold_check("board_rows", len(board), 224, "eq", "Demo should cover the full 2025 drafted-player class."),
        threshold_check("player_details", len(details), len(board), "eq", "Every board row should have a player detail payload."),
        threshold_check(
            "details_have_stat_evidence",
            sum(1 for detail in details if "stat_evidence" in detail),
            len(details),
            "eq",
            "Every player detail should include role-aware stat evidence.",
        ),
        threshold_check(
            "low_evidence_players",
            count_rows(board, "evidence_depth", "low"),
            30,
            "lte",
            "Low-evidence count should stay at or below the current demo tolerance.",
        ),
        threshold_check(
            "top_50_consensus_overlap",
            top_n_overlap(board, 50),
            45,
            "gte",
            "Top 50 should remain anchored enough for a recent-class business demo.",
        ),
        named_rank_check(board_by_name, "Matthew Schaefer", 5, "Elite defense calibration should remain top-tier."),
        named_rank_check(board_by_name, "Michael Misa", 5, "Trust-anchor forward should remain top-tier."),
        named_rank_check(board_by_name, "Porter Martone", 5, "Trust-anchor forward should remain top-tier."),
        named_rank_check(board_by_name, "Pyotr Andreyanov", 40, "Goalie evidence story should stay visible in the top half."),
        content_check(
            "misa_sjs_center_pipeline",
            str(misa_sjs.get("role_type", "")).endswith("center"),
            "Composite center/wing positions should use the primary center pipeline.",
        ),
        content_check(
            "schaefer_nyi_fit_above_chicago",
            float_value(schaefer_nyi.get("score")) - float_value(schaefer_chi.get("score")) >= 0.02,
            "NYI should retain a meaningful fit advantage over Chicago's defense-heavy U25 pipeline.",
        ),
        content_check(
            "misa_sjs_pipeline_need_bounded",
            0.0 < float_value(misa_sjs.get("pipeline_need_score")) <= 0.35,
            "San Jose's established U25 center group should materially limit additional center need.",
        ),
        content_check("prospect_stats_evidence_ui", "Prospect Stats Evidence" in html, "Player detail should show stat evidence section."),
        content_check("production_header", "<th>Production</th>" in html, "History table should use role-neutral production label."),
        content_check(
            "guided_demo_preset",
            all(
                marker in html
                for marker in ("Start Guided Demo", "guided-previous", "guided-next")
            ),
            "Demo site should retain the presenter-mode story controls.",
        ),
        content_check(
            "meeting_brief_html",
            brief_html.is_file() and "Guided Draft Meeting Brief" in brief_html.read_text(encoding="utf-8"),
            "Readiness build should generate the printable guided-story brief.",
        ),
        content_check(
            "meeting_brief_pdf",
            brief_pdf.is_file() and brief_pdf.stat().st_size > 1_000,
            "Readiness build should generate a non-empty one-page PDF brief.",
        ),
    ]
    return DemoAcceptanceReport(checks=checks)


def baseline_acceptance_checks(
    baseline: dict[str, object],
    manifest: dict[str, object],
    board: list[dict[str, str]],
    details: list[dict[str, object]],
) -> list[AcceptanceCheck]:
    if not baseline:
        return [
            content_check(
                "baseline_present",
                False,
                "Demo package must include the canonical baseline.json artifact.",
            )
        ]
    baseline_id = str(baseline.get("baseline_id", ""))
    manifest_id = str(manifest.get("baseline_id", ""))
    expected = baseline.get("metrics", {})
    expected_metrics = expected if isinstance(expected, dict) else {}
    manifest_metrics = manifest.get("baseline_metrics", {})
    actual_metrics = artifact_metrics(board, details)
    return [
        content_check(
            "baseline_present",
            bool(baseline_id),
            "Demo package must include a non-empty canonical baseline identity.",
        ),
        content_check(
            "baseline_manifest_identity",
            bool(baseline_id) and baseline_id == manifest_id,
            "Manifest and baseline must reference the same dataset fingerprint.",
        ),
        value_check(
            "baseline_player_count",
            len(board),
            expected_metrics.get("player_count"),
            "Board rows must match the canonical dataset player count.",
        ),
        value_check(
            "baseline_player_details",
            len(details),
            expected_metrics.get("player_count"),
            "Player payload rows must match the canonical dataset player count.",
        ),
        content_check(
            "baseline_manifest_metrics",
            expected_metrics == manifest_metrics,
            "Manifest must embed the exact canonical baseline metrics.",
        ),
        content_check(
            "baseline_board_metrics",
            all(
                actual_metrics.get(key) == expected_metrics.get(key)
                for key in (
                    "board_row_count",
                    "player_detail_count",
                    "evidence_depth_counts",
                    "top_50_consensus_overlap",
                    "average_absolute_consensus_delta",
                )
            ),
            "Board and player artifacts must reproduce the canonical baseline metrics.",
        ),
    ]


def format_demo_acceptance_report(report: DemoAcceptanceReport) -> str:
    lines = [
        "# Demo Acceptance Report",
        "",
        f"- Status: {'pass' if report.passed else 'fail'}",
        f"- Checks: {len(report.checks)}",
        f"- Failed: {report.failed_count}",
        "",
        "| Check | Status | Actual | Expected | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for check in report.checks:
        lines.append(
            f"| {check.check_id} | {check.status} | {check.actual} | {check.expected} | {check.detail} |"
        )
    return "\n".join(lines) + "\n"


def threshold_check(check_id: str, actual: int, expected: int, operator: str, detail: str) -> AcceptanceCheck:
    passed = {
        "eq": actual == expected,
        "lte": actual <= expected,
        "gte": actual >= expected,
    }[operator]
    expected_label = {"eq": "=", "lte": "<=", "gte": ">="}[operator]
    return AcceptanceCheck(
        check_id=check_id,
        status="pass" if passed else "fail",
        actual=str(actual),
        expected=f"{expected_label} {expected}",
        detail=detail,
    )


def named_rank_check(board_by_name: dict[str, dict[str, str]], name: str, max_rank: int, detail: str) -> AcceptanceCheck:
    row = board_by_name.get(name)
    if row is None:
        return AcceptanceCheck(
            check_id=f"{slug(name)}_rank",
            status="fail",
            actual="missing",
            expected=f"<= {max_rank}",
            detail=detail,
        )
    rank = int_value(row.get("board_rank"))
    return threshold_check(f"{slug(name)}_rank", rank, max_rank, "lte", detail)


def content_check(check_id: str, passed: bool, detail: str) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id=check_id,
        status="pass" if passed else "fail",
        actual="present" if passed else "missing",
        expected="present",
        detail=detail,
    )


def value_check(
    check_id: str,
    actual: object,
    expected: object,
    detail: str,
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id=check_id,
        status="pass" if actual == expected else "fail",
        actual=str(actual),
        expected=str(expected),
        detail=detail,
    )


def count_rows(rows: list[dict[str, str]], key: str, value: str) -> int:
    return sum(1 for row in rows if row.get(key) == value)


def team_fit_option(detail: dict[str, object], team_id: str) -> dict[str, object]:
    return next(
        (option for option in detail.get("team_fit_options", []) if option.get("team_id") == team_id),
        {},
    )


def top_n_overlap(rows: list[dict[str, str]], n: int) -> int:
    board_top = {row["player_id"] for row in rows if int_value(row.get("board_rank")) <= n}
    consensus_top = {row["player_id"] for row in rows if int_value(row.get("consensus_rank")) <= n}
    return len(board_top & consensus_top)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def int_value(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def float_value(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def slug(value: str) -> str:
    return "_".join(value.lower().split())
