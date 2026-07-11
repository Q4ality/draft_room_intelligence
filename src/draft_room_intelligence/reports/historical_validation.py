"""Historical outcome-validation reports for draft-board scoring approaches."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.domain import HistoricalProspect
from draft_room_intelligence.evaluation.baselines import (
    adjusted_production_scores,
    consensus_scores,
    contextual_scores,
    evaluate_board_order,
    evaluate_historical_scores,
    projection_scores,
    role_aware_scores,
    role_specific_hybrid_scores,
    weighted_hybrid_scores,
)
from draft_room_intelligence.projection.baseline import project_board


DEFAULT_BASELINES = (
    "consensus",
    "projection",
    "adjusted-production",
    "contextual",
    "role-aware",
    "role-specific-hybrid",
    "hybrid",
)

SUMMARY_COLUMNS = [
    "baseline",
    "prospects",
    "nhler_precision_at_n",
    "impact_precision_at_n",
    "bust_precision_at_n",
    "spearman_nhl_games",
    "top_n_avg_nhl_games",
    "top_n_avg_nhl_points",
    "top_n_games_lift",
    "top_n_points_lift",
    "top_n_nhlers",
    "top_n_impact_players",
    "top_n_busts",
    "nhler_precision_delta_vs_consensus",
    "impact_precision_delta_vs_consensus",
    "spearman_delta_vs_consensus",
    "games_lift_delta_vs_consensus",
]


@dataclass(frozen=True)
class HistoricalValidationReport:
    data_path: Path
    prospect_count: int
    draft_years: tuple[int, ...]
    precision_n: int
    top_n: int
    rows: list[dict[str, str]]


def build_historical_validation_report(
    prospects: list[HistoricalProspect],
    data_path: Path,
    *,
    baselines: tuple[str, ...] = DEFAULT_BASELINES,
    precision_n: int = 25,
    top_n: int = 25,
) -> HistoricalValidationReport:
    if not prospects:
        raise ValueError("at least one historical prospect is required")

    rows = []
    consensus_row: dict[str, str] | None = None
    for baseline in baselines:
        scores = score_baseline(prospects, baseline)
        probability_report = evaluate_historical_scores(prospects, scores, precision_n=precision_n)
        board_report = evaluate_board_order(prospects, scores, top_ns=(top_n,))
        board_key = f"top_{top_n}"
        board_metrics = board_report[board_key]
        row = {
            "baseline": baseline,
            "prospects": str(len(prospects)),
            "nhler_precision_at_n": fmt(probability_report["nhler"]["precision_at_n"]),
            "impact_precision_at_n": fmt(probability_report["impact"]["precision_at_n"]),
            "bust_precision_at_n": fmt(probability_report["bust"]["precision_at_n"]),
            "spearman_nhl_games": fmt(probability_report["rank"]["spearman_nhl_games"]),
            "top_n_avg_nhl_games": fmt(board_metrics["avg_nhl_games"]),
            "top_n_avg_nhl_points": fmt(board_metrics["avg_nhl_points"]),
            "top_n_games_lift": fmt(board_metrics["games_lift"]),
            "top_n_points_lift": fmt(board_metrics["points_lift"]),
            "top_n_nhlers": fmt(board_metrics["nhlers"]),
            "top_n_impact_players": fmt(board_metrics["impact_players"]),
            "top_n_busts": fmt(board_metrics["busts"]),
            "nhler_precision_delta_vs_consensus": "",
            "impact_precision_delta_vs_consensus": "",
            "spearman_delta_vs_consensus": "",
            "games_lift_delta_vs_consensus": "",
        }
        if baseline == "consensus":
            consensus_row = row
        elif consensus_row is not None:
            row["nhler_precision_delta_vs_consensus"] = fmt(
                float(row["nhler_precision_at_n"]) - float(consensus_row["nhler_precision_at_n"])
            )
            row["impact_precision_delta_vs_consensus"] = fmt(
                float(row["impact_precision_at_n"]) - float(consensus_row["impact_precision_at_n"])
            )
            row["spearman_delta_vs_consensus"] = fmt(
                float(row["spearman_nhl_games"]) - float(consensus_row["spearman_nhl_games"])
            )
            row["games_lift_delta_vs_consensus"] = fmt(
                float(row["top_n_games_lift"]) - float(consensus_row["top_n_games_lift"])
            )
        rows.append(row)

    return HistoricalValidationReport(
        data_path=data_path,
        prospect_count=len(prospects),
        draft_years=tuple(sorted({prospect.draft_year for prospect in prospects})),
        precision_n=precision_n,
        top_n=top_n,
        rows=rows,
    )


def score_baseline(prospects: list[HistoricalProspect], baseline: str) -> dict[str, float]:
    if baseline == "consensus":
        return consensus_scores(prospects)
    if baseline == "projection":
        projection_inputs = [prospect.to_projection_prospect() for prospect in prospects]
        return projection_scores(project_board(projection_inputs))
    if baseline == "adjusted-production":
        return adjusted_production_scores(prospects)
    if baseline == "contextual":
        return contextual_scores(prospects)
    if baseline == "role-aware":
        return role_aware_scores(prospects)
    if baseline == "role-specific-hybrid":
        return role_specific_hybrid_scores(prospects)
    if baseline == "hybrid":
        projection_inputs = [prospect.to_projection_prospect() for prospect in prospects]
        return weighted_hybrid_scores(
            [
                (consensus_scores(prospects), 0.5),
                (projection_scores(project_board(projection_inputs)), 0.3),
                (adjusted_production_scores(prospects), 0.2),
            ]
        )
    raise ValueError(f"unsupported baseline: {baseline}")


def write_historical_validation_report(
    output_dir: str | Path,
    prospects: list[HistoricalProspect],
    data_path: Path,
    *,
    precision_n: int = 25,
    top_n: int = 25,
    baselines: tuple[str, ...] = DEFAULT_BASELINES,
) -> HistoricalValidationReport:
    report = build_historical_validation_report(
        prospects,
        data_path,
        baselines=baselines,
        precision_n=precision_n,
        top_n=top_n,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_summary_csv(root / "summary.csv", report.rows)
    (root / "summary.md").write_text(format_historical_validation_report(report), encoding="utf-8")
    return report


def write_summary_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def format_historical_validation_report(report: HistoricalValidationReport) -> str:
    best_games = max(report.rows, key=lambda row: float(row["top_n_games_lift"]))
    best_spearman = max(report.rows, key=lambda row: float(row["spearman_nhl_games"]))
    draft_years = ", ".join(str(year) for year in report.draft_years)
    lines = [
        "# Historical Validation Report",
        "",
        f"- Data path: `{report.data_path}`",
        f"- Draft years: {draft_years}",
        f"- Prospects: {report.prospect_count}",
        f"- Precision@N: {report.precision_n}",
        f"- Board top-N: {report.top_n}",
        "",
        "## Headline",
        "",
        (
            f"- Best top-{report.top_n} NHL-games lift: `{best_games['baseline']}` "
            f"at {best_games['top_n_games_lift']}x."
        ),
        (
            f"- Best rank correlation to NHL games: `{best_spearman['baseline']}` "
            f"at {best_spearman['spearman_nhl_games']}."
        ),
        "",
        "## Baseline Comparison",
        "",
        (
            "| Baseline | NHLer P@N | Impact P@N | Spearman Games | "
            f"Top {report.top_n} Games Lift | Delta vs Consensus |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.rows:
        lines.append(
            "| {baseline} | {nhler_precision_at_n} | {impact_precision_at_n} | "
            "{spearman_nhl_games} | {top_n_games_lift} | {games_lift_delta_vs_consensus} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Treat this as an initial validation slice, not a final model claim.",
            "- A single draft class can show whether the workflow is directionally sane, but it cannot establish durable predictive lift.",
            "- The next validation step is adding multiple older draft classes with comparable pre-draft histories and outcome labels.",
        ]
    )
    return "\n".join(lines) + "\n"


def fmt(value: float) -> str:
    return f"{value:.3f}"
