"""Acceptance checks for business-demo readiness."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


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
    html = (root / "index.html").read_text(encoding="utf-8")
    board_by_name = {row["name"]: row for row in board}
    checks = [
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
        content_check("prospect_stats_evidence_ui", "Prospect Stats Evidence" in html, "Player detail should show stat evidence section."),
        content_check("production_header", "<th>Production</th>" in html, "History table should use role-neutral production label."),
    ]
    return DemoAcceptanceReport(checks=checks)


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


def count_rows(rows: list[dict[str, str]], key: str, value: str) -> int:
    return sum(1 for row in rows if row.get(key) == value)


def top_n_overlap(rows: list[dict[str, str]], n: int) -> int:
    board_top = {row["player_id"] for row in rows if int_value(row.get("board_rank")) <= n}
    consensus_top = {row["player_id"] for row in rows if int_value(row.get("consensus_rank")) <= n}
    return len(board_top & consensus_top)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def slug(value: str) -> str:
    return "_".join(value.lower().split())
