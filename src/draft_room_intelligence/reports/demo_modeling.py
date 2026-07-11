"""Sanity-check demo board movement versus consensus ordering."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


MOVEMENT_COLUMNS = [
    "movement_rank",
    "player_id",
    "name",
    "position",
    "role_group",
    "board_rank",
    "consensus_rank",
    "rank_delta",
    "abs_rank_delta",
    "disagreement_bucket",
    "evidence_depth",
    "primary_league",
    "model_score",
    "board_score",
    "short_reason",
    "risk_note",
]


@dataclass(frozen=True)
class RoleMovement:
    role_group: str
    count: int
    avg_abs_delta: float
    model_higher: int
    consensus_higher: int
    aligned: int
    high_or_medium_moves: int


@dataclass(frozen=True)
class DemoModelingReport:
    manifest: dict[str, object]
    board_rows: list[dict[str, str]]
    movement_rows: list[dict[str, str]]
    role_movements: list[RoleMovement]
    disagreement_counts: Counter[str]
    evidence_counts: Counter[str]
    moved_10_plus: int
    high_or_medium_moved_10_plus: int
    avg_abs_delta: float
    top_n_overlap: dict[str, int]


def build_demo_modeling_report(demo_output_dir: str | Path, *, top_n: int = 30) -> DemoModelingReport:
    root = Path(demo_output_dir)
    manifest = read_manifest(root / "manifest.json")
    board_rows = read_csv(root / "board.csv")
    movement_rows = [
        build_movement_row(row, movement_rank=index)
        for index, row in enumerate(
            sorted(board_rows, key=lambda row: (-abs(rank_delta(row)), int_value(row, "board_rank"), row["name"]))[
                :top_n
            ],
            start=1,
        )
    ]
    moved_10_plus_rows = [row for row in board_rows if abs(rank_delta(row)) >= 10]
    high_or_medium_moved = [
        row for row in moved_10_plus_rows if row.get("evidence_depth") in {"high", "medium"}
    ]
    return DemoModelingReport(
        manifest=manifest,
        board_rows=board_rows,
        movement_rows=movement_rows,
        role_movements=build_role_movements(board_rows),
        disagreement_counts=Counter(row["disagreement_bucket"] for row in board_rows),
        evidence_counts=Counter(row["evidence_depth"] for row in board_rows),
        moved_10_plus=len(moved_10_plus_rows),
        high_or_medium_moved_10_plus=len(high_or_medium_moved),
        avg_abs_delta=average([abs(rank_delta(row)) for row in board_rows]),
        top_n_overlap={
            "top_10": top_n_overlap(board_rows, 10),
            "top_25": top_n_overlap(board_rows, 25),
            "top_50": top_n_overlap(board_rows, 50),
        },
    )


def write_demo_modeling_report(
    demo_output_dir: str | Path,
    output_dir: str | Path,
    *,
    top_n: int = 30,
) -> DemoModelingReport:
    report = build_demo_modeling_report(demo_output_dir, top_n=top_n)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "largest_movements.csv", MOVEMENT_COLUMNS, report.movement_rows)
    (root / "summary.md").write_text(format_demo_modeling_report(report), encoding="utf-8")
    return report


def format_demo_modeling_report(report: DemoModelingReport) -> str:
    manifest = report.manifest
    lines = [
        "# Demo Modeling Sanity Report",
        "",
        "## Snapshot",
        "",
        f"- Draft year: {manifest.get('draft_year', 'unknown')}",
        f"- Players: {manifest.get('player_count', len(report.board_rows))}",
        f"- Dataset status: `{manifest.get('dataset_status', 'unknown')}`",
        f"- Average absolute board-vs-consensus movement: {report.avg_abs_delta:.1f} slots",
        f"- Players moved 10+ slots: {report.moved_10_plus}",
        f"- 10+ slot moves with high/medium evidence: {report.high_or_medium_moved_10_plus}",
        "",
        "## Top-N Overlap With Consensus",
        "",
    ]
    for bucket, overlap in report.top_n_overlap.items():
        n = bucket.split("_")[1]
        lines.append(f"- Top {n}: {overlap} shared players")
    lines.extend(["", "## Disagreement Buckets", ""])
    for bucket, count in report.disagreement_counts.most_common():
        lines.append(f"- {bucket}: {count}")
    lines.extend(["", "## Role Movement", ""])
    lines.append("| Role | Players | Avg Abs Move | Model Higher | Consensus Higher | Aligned | 10+ Moves With Usable Evidence |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for role in report.role_movements:
        lines.append(
            f"| {role.role_group} | {role.count} | {role.avg_abs_delta:.1f} | "
            f"{role.model_higher} | {role.consensus_higher} | {role.aligned} | {role.high_or_medium_moves} |"
        )
    lines.extend(["", "## Largest Board Movements", ""])
    lines.append("| Move | Player | Role | Board | Consensus | Evidence | League | Reason |")
    lines.append("| ---: | --- | --- | ---: | ---: | --- | --- | --- |")
    for row in report.movement_rows[:15]:
        lines.append(
            "| {rank_delta} | {name} | {role_group} | {board_rank} | {consensus_rank} | "
            "{evidence_depth} | {primary_league} | {short_reason} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This is a recent-class demo sanity check, not outcome validation.",
            "- The current board is meaningfully different from pure consensus, but still evidence-weighted.",
            "- High/medium evidence movement cases are the safest stories to present.",
            "- Low-evidence movement cases should be treated as data-gap prompts before business demos.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_role_movements(rows: list[dict[str, str]]) -> list[RoleMovement]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["role_group"]].append(row)
    movements: list[RoleMovement] = []
    for role, role_rows in sorted(grouped.items()):
        movements.append(
            RoleMovement(
                role_group=role,
                count=len(role_rows),
                avg_abs_delta=average([abs(rank_delta(row)) for row in role_rows]),
                model_higher=sum(1 for row in role_rows if row["disagreement_bucket"] == "model_higher"),
                consensus_higher=sum(1 for row in role_rows if row["disagreement_bucket"] == "consensus_higher"),
                aligned=sum(1 for row in role_rows if row["disagreement_bucket"] == "aligned"),
                high_or_medium_moves=sum(
                    1
                    for row in role_rows
                    if abs(rank_delta(row)) >= 10 and row["evidence_depth"] in {"high", "medium"}
                ),
            )
        )
    return movements


def build_movement_row(row: dict[str, str], *, movement_rank: int) -> dict[str, str]:
    delta = rank_delta(row)
    return {
        "movement_rank": str(movement_rank),
        "player_id": row["player_id"],
        "name": row["name"],
        "position": row["position"],
        "role_group": row["role_group"],
        "board_rank": row["board_rank"],
        "consensus_rank": row["consensus_rank"],
        "rank_delta": str(delta),
        "abs_rank_delta": str(abs(delta)),
        "disagreement_bucket": row["disagreement_bucket"],
        "evidence_depth": row["evidence_depth"],
        "primary_league": row["primary_league"],
        "model_score": row["model_score"],
        "board_score": row["board_score"],
        "short_reason": row["short_reason"],
        "risk_note": row["risk_note"],
    }


def top_n_overlap(rows: list[dict[str, str]], n: int) -> int:
    board_top = {row["player_id"] for row in rows if int_value(row, "board_rank") <= n}
    consensus_top = {row["player_id"] for row in rows if int_value(row, "consensus_rank") <= n}
    return len(board_top & consensus_top)


def rank_delta(row: dict[str, str]) -> int:
    return int_value(row, "consensus_rank") - int_value(row, "board_rank")


def average(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


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
