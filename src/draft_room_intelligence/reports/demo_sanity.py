"""Focused demo sanity report for board, role, and story-player checks."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


TOP_BOARD_COLUMNS = [
    "board_rank",
    "name",
    "position",
    "role_group",
    "consensus_rank",
    "model_score",
    "board_score",
    "team_adjusted_score",
    "ep_tool_score",
    "team_fit_score",
    "short_reason",
]

STORY_COLUMNS = [
    "name",
    "board_rank",
    "consensus_rank",
    "position",
    "role_group",
    "model_score",
    "board_score",
    "team_adjusted_score",
    "stat_evidence",
    "why_high",
    "risk_flags",
]


@dataclass(frozen=True)
class DemoSanityReport:
    board_rows: list[dict[str, str]]
    player_details: list[dict[str, object]]
    top_overall: list[dict[str, str]]
    top_defense: list[dict[str, str]]
    top_goalies: list[dict[str, str]]
    biggest_disagreements: list[dict[str, str]]
    story_rows: list[dict[str, str]]


def write_demo_sanity_report(demo_output_dir: str | Path, output_dir: str | Path) -> DemoSanityReport:
    report = build_demo_sanity_report(demo_output_dir)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "top_20_overall.csv", TOP_BOARD_COLUMNS, report.top_overall)
    write_csv(root / "top_10_defense.csv", TOP_BOARD_COLUMNS, report.top_defense)
    write_csv(root / "top_10_goalies.csv", TOP_BOARD_COLUMNS, report.top_goalies)
    write_csv(root / "biggest_disagreements.csv", TOP_BOARD_COLUMNS + ["rank_delta"], report.biggest_disagreements)
    write_csv(root / "story_player_checks.csv", STORY_COLUMNS, report.story_rows)
    (root / "summary.md").write_text(format_demo_sanity_report(report), encoding="utf-8")
    return report


def build_demo_sanity_report(demo_output_dir: str | Path) -> DemoSanityReport:
    root = Path(demo_output_dir)
    board_rows = read_csv(root / "board.csv")
    player_details = json.loads((root / "players.json").read_text(encoding="utf-8"))
    players_by_name = {detail["header"]["name"]: detail for detail in player_details}
    top_overall = [project_board_row(row) for row in sorted_by_board_rank(board_rows)[:20]]
    top_defense = [project_board_row(row) for row in sorted_by_board_rank(filter_role(board_rows, "defense"))[:10]]
    top_goalies = [project_board_row(row) for row in sorted_by_board_rank(filter_role(board_rows, "goalie"))[:10]]
    disagreements = sorted(
        board_rows,
        key=lambda row: (-abs(rank_delta(row)), int_value(row, "board_rank"), row["name"]),
    )[:20]
    biggest_disagreements = [project_board_row(row) | {"rank_delta": str(rank_delta(row))} for row in disagreements]
    story_rows = [build_story_row(name, board_rows, players_by_name) for name in story_player_names()]
    return DemoSanityReport(
        board_rows=board_rows,
        player_details=player_details,
        top_overall=top_overall,
        top_defense=top_defense,
        top_goalies=top_goalies,
        biggest_disagreements=biggest_disagreements,
        story_rows=story_rows,
    )


def format_demo_sanity_report(report: DemoSanityReport) -> str:
    lines = [
        "# Demo Sanity Report",
        "",
        "## Score Interpretation",
        "",
        "- `model_score` remains production/stat-sensitive and can be lower for shortened samples.",
        "- `board_score` blends model, consensus, EP guide evidence, and role-aware calibration.",
        "- `team_adjusted_score` adds roster-fit context for the selected/drafted team view.",
        "",
        "## Top 20 Overall",
        "",
        format_table(report.top_overall, ["board_rank", "name", "position", "consensus_rank", "board_score", "model_score"]),
        "",
        "## Top 10 Defense",
        "",
        format_table(report.top_defense, ["board_rank", "name", "consensus_rank", "board_score", "model_score"]),
        "",
        "## Top 10 Goalies",
        "",
        format_table(report.top_goalies, ["board_rank", "name", "consensus_rank", "board_score", "model_score"]),
        "",
        "## Biggest Board-vs-Consensus Disagreements",
        "",
        format_table(report.biggest_disagreements[:10], ["rank_delta", "board_rank", "name", "role_group", "consensus_rank", "short_reason"]),
        "",
        "## Story Player Checks",
        "",
        format_table(report.story_rows, ["name", "board_rank", "consensus_rank", "position", "stat_evidence"]),
        "",
        "## Acceptance Notes",
        "",
        "- Matthew Schaefer should remain top-tier while still exposing his lower pure `model_score` from a 19-game captured sample.",
        "- Michael Misa and Porter Martone should remain credible top-forward anchors.",
        "- Alexei Medvedev and Pyotr Andreyanov should show goalie-specific evidence instead of skater point proxies.",
    ]
    return "\n".join(lines) + "\n"


def build_story_row(
    name: str,
    board_rows: list[dict[str, str]],
    players_by_name: dict[str, dict[str, object]],
) -> dict[str, str]:
    board = next((row for row in board_rows if row["name"] == name), {})
    detail = players_by_name.get(name, {})
    stats = detail.get("stat_evidence", {}) if detail else {}
    if isinstance(stats, dict) and stats.get("role_group") == "goalie":
        stat_evidence = (
            f"{stats.get('goalie_games', 0)} GP, "
            f"{float_value(stats.get('goalie_save_percentage')):.3f} SV%, "
            f"{float_value(stats.get('goalie_goals_against_average')):.2f} GAA, "
            f"{stats.get('goalie_shutouts', 0)} SO"
        )
    elif isinstance(stats, dict):
        stat_evidence = (
            f"{stats.get('games', 0)} GP, "
            f"{stats.get('goals', 0)}-{stats.get('assists', 0)}-{stats.get('points', 0)}, "
            f"{float_value(stats.get('points_per_game')):.3f} PPG"
        )
    else:
        stat_evidence = ""
    return {
        "name": name,
        "board_rank": board.get("board_rank", ""),
        "consensus_rank": board.get("consensus_rank", ""),
        "position": board.get("position", ""),
        "role_group": board.get("role_group", ""),
        "model_score": board.get("model_score", ""),
        "board_score": board.get("board_score", ""),
        "team_adjusted_score": board.get("team_adjusted_score", ""),
        "stat_evidence": stat_evidence,
        "why_high": " | ".join(detail.get("why_high", [])) if detail else "",
        "risk_flags": " | ".join(detail.get("risk_flags", [])) if detail else "",
    }


def story_player_names() -> list[str]:
    return [
        "Matthew Schaefer",
        "Michael Misa",
        "Porter Martone",
        "Alexei Medvedev",
        "Pyotr Andreyanov",
        "Alexander Zharovsky",
    ]


def project_board_row(row: dict[str, str]) -> dict[str, str]:
    return {column: row.get(column, "") for column in TOP_BOARD_COLUMNS}


def sorted_by_board_rank(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: int_value(row, "board_rank"))


def filter_role(rows: list[dict[str, str]], role_group: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get("role_group") == role_group]


def format_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def rank_delta(row: dict[str, str]) -> int:
    return int_value(row, "consensus_rank") - int_value(row, "board_rank")


def int_value(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def float_value(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
