"""Prioritize demo data gaps from generated demo export artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

GAP_COLUMNS = [
    "priority_rank",
    "priority_score",
    "player_id",
    "name",
    "position",
    "role_group",
    "board_rank",
    "consensus_rank",
    "primary_league",
    "primary_league_family",
    "primary_competition_level",
    "disagreement_bucket",
    "pre_draft_row_count",
    "pre_draft_league_count",
    "adult_game_share",
    "playoff_game_share",
    "playoff_evidence_status",
    "suggested_source_strategy",
    "gap_reason",
]


@dataclass(frozen=True)
class DemoGapReport:
    manifest: dict[str, object]
    low_evidence_rows: list[dict[str, str]]
    priority_rows: list[dict[str, str]]
    league_counts: Counter[str]
    strategy_counts: Counter[str]


def build_demo_gap_report(demo_output_dir: str | Path, *, top_n: int = 30) -> DemoGapReport:
    root = Path(demo_output_dir)
    manifest = read_manifest(root / "manifest.json")
    board_rows = read_csv(root / "board.csv")
    low_rows = [row for row in board_rows if row.get("evidence_depth") == "low"]
    prioritized = sorted(low_rows, key=gap_sort_key)
    priority_rows = [
        build_gap_row(row, priority_rank=index)
        for index, row in enumerate(prioritized[:top_n], start=1)
    ]
    return DemoGapReport(
        manifest=manifest,
        low_evidence_rows=low_rows,
        priority_rows=priority_rows,
        league_counts=Counter(row["primary_league"] for row in low_rows),
        strategy_counts=Counter(row["suggested_source_strategy"] for row in priority_rows),
    )


def write_demo_gap_report(
    demo_output_dir: str | Path,
    output_dir: str | Path,
    *,
    top_n: int = 30,
) -> DemoGapReport:
    report = build_demo_gap_report(demo_output_dir, top_n=top_n)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "priority_gaps.csv", GAP_COLUMNS, report.priority_rows)
    (root / "summary.md").write_text(format_demo_gap_report(report), encoding="utf-8")
    return report


def format_demo_gap_report(report: DemoGapReport) -> str:
    manifest = report.manifest
    lines = [
        "# Demo Data Gap Report",
        "",
        "## Snapshot",
        "",
        f"- Draft year: {manifest.get('draft_year', 'unknown')}",
        f"- Players: {manifest.get('player_count', 'unknown')}",
        f"- Dataset status: `{manifest.get('dataset_status', 'unknown')}`",
        f"- Low-evidence players: {len(report.low_evidence_rows)}",
        "",
        "## Low-Evidence League Clusters",
        "",
    ]
    for league, count in report.league_counts.most_common(12):
        lines.append(f"- {league}: {count}")
    lines.extend(["", "## Priority Source Strategies", ""])
    for strategy, count in report.strategy_counts.most_common():
        lines.append(f"- {strategy}: {count}")
    lines.extend(["", "## Top Priority Players", ""])
    lines.append(
        "| Priority | Player | Pos | Board | Consensus | League | Strategy | Reason |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in report.priority_rows:
        lines.append(
            "| {priority_rank} | {name} | {position} | {board_rank} | {consensus_rank} | "
            "{primary_league} | {suggested_source_strategy} | {gap_reason} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Recommended Next Data Work",
            "",
            (
                "1. Close the highest-ranked low-evidence players that also have "
                "model/consensus disagreement."
            ),
            (
                "2. Work by source family so each pass improves a visible cluster, "
                "not just one player."
            ),
            "3. Rebuild the demo and compare high/medium/low evidence movement after each pass.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_gap_row(row: dict[str, str], *, priority_rank: int) -> dict[str, str]:
    score = priority_score(row)
    strategy = suggested_source_strategy(row)
    return {
        "priority_rank": str(priority_rank),
        "priority_score": f"{score:.3f}",
        "player_id": row["player_id"],
        "name": row["name"],
        "position": row["position"],
        "role_group": row["role_group"],
        "board_rank": row["board_rank"],
        "consensus_rank": row["consensus_rank"],
        "primary_league": row["primary_league"],
        "primary_league_family": row["primary_league_family"],
        "primary_competition_level": row["primary_competition_level"],
        "disagreement_bucket": row["disagreement_bucket"],
        "pre_draft_row_count": row["pre_draft_row_count"],
        "pre_draft_league_count": row["pre_draft_league_count"],
        "adult_game_share": row["adult_game_share"],
        "playoff_game_share": row["playoff_game_share"],
        "playoff_evidence_status": playoff_evidence_status(row),
        "suggested_source_strategy": strategy,
        "gap_reason": gap_reason(row, strategy),
    }


def gap_sort_key(row: dict[str, str]) -> tuple[float, int, str]:
    return (-priority_score(row), int_value(row, "board_rank"), row["name"])


def priority_score(row: dict[str, str]) -> float:
    board_rank = int_value(row, "board_rank")
    consensus_rank = int_value(row, "consensus_rank")
    score = max(0.0, (225 - board_rank) / 224) * 60
    score += max(0.0, (225 - consensus_rank) / 224) * 20
    if row.get("disagreement_bucket") != "aligned":
        score += 12
    if row.get("position") == "G":
        score += 8
    if float_value(row, "adult_game_share") > 0:
        score += 6
    if playoff_evidence_status(row) == "unavailable":
        score += 2
    if int_value(row, "pre_draft_row_count") <= 1:
        score += 5
    return score


def suggested_source_strategy(row: dict[str, str]) -> str:
    league = row.get("primary_league", "")
    family = row.get("primary_league_family", "")
    position = row.get("position", "")
    if position == "G":
        if league in {"MHL", "KHL", "VHL"} or family == "Russia Junior":
            return "Russian goalie stats"
        if league in {"QMJHL", "OHL", "WHL"}:
            return "CHL goalie stats"
        return "Goalie stat source"
    if league in {"MHL", "KHL", "VHL"} or family.startswith("Russia"):
        return "Russian KHL/MHL/VHL"
    if league in {"Sweden Jrs.", "SHL", "HockeyAllsvenskan"} or family == "Sweden":
        return "Sweden SHL/J20"
    if league in {"Liiga", "Finland Jrs.", "U20", "Mestis"} or family == "Finland":
        return "Finland Liiga/U20"
    if league in {"USHL", "NCAA"} or family in {"USHL", "College"}:
        return "NCAA/USHL/USNTDP"
    if league in {"OHL", "WHL", "QMJHL"}:
        return "CHL skater/playoff"
    if league in {"High School", "Prep School", "USHS"}:
        return "US high-school/prep"
    if league in {"Czech", "Czech. Jr", "DEL", "Switzerland Jrs."}:
        return "European fallback source"
    return "Open-stats fallback"


def gap_reason(row: dict[str, str], strategy: str) -> str:
    reasons = ["low evidence"]
    if row.get("disagreement_bucket") != "aligned":
        reasons.append(row["disagreement_bucket"].replace("_", " "))
    if int_value(row, "pre_draft_row_count") <= 1:
        reasons.append("single stat row")
    playoff_status = playoff_evidence_status(row)
    if playoff_status == "covered_no_appearance":
        reasons.append("no playoff appearance found")
    elif playoff_status == "unavailable":
        reasons.append("playoff source unavailable")
    if float_value(row, "adult_game_share") > 0:
        reasons.append("adult exposure needs verification")
    return "; ".join(reasons) + f"; source family: {strategy}"


def playoff_evidence_status(row: dict[str, str]) -> str:
    if float_value(row, "playoff_game_share") > 0:
        return "playoff_experience"
    if (
        row.get("primary_league") in {"OHL", "WHL", "QMJHL"}
        and int_value(row, "pre_draft_row_count") > 0
    ):
        return "covered_no_appearance"
    return "unavailable"


def read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def float_value(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "0") or 0)
    except ValueError:
        return 0.0
