"""Temporal slot-and-role baseline for audited NHL outcome labels."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from draft_room_intelligence.evaluation.metrics import brier_score, precision_at_n
from draft_room_intelligence.reports.longitudinal_outcomes import (
    OutcomeLabel,
    eligible_outcome_labels,
    load_outcome_labels,
)

FEATURE_NAMES = ("slot_score", "is_defense", "is_goalie")


@dataclass(frozen=True)
class BaselineExample:
    player_id: str
    draft_year: int
    overall_pick: int
    position: str
    nhl_games: int
    nhl_points: int
    goalie_starts: int

    @property
    def role(self) -> str:
        if self.position == "G":
            return "goalie"
        if self.position == "D":
            return "defense"
        return "forward"

    @property
    def is_regular_nhler(self) -> bool:
        return self.nhl_games >= 100

    @property
    def is_impact_player(self) -> bool:
        return self.goalie_starts >= 25 if self.role == "goalie" else self.nhl_points >= 50

    def features(self, max_pick: int) -> tuple[float, ...]:
        slot_score = 1.0 - ((self.overall_pick - 1) / max(1, max_pick - 1))
        return (
            slot_score,
            float(self.role == "defense"),
            float(self.role == "goalie"),
        )


@dataclass(frozen=True)
class FittedBaselineModel:
    target: str
    intercept: float
    weights: tuple[float, ...]
    constant_probability: float | None

    def predict(self, features: tuple[float, ...]) -> float:
        if self.constant_probability is not None:
            return self.constant_probability
        return sigmoid(
            self.intercept + sum(weight * value for weight, value in zip(self.weights, features))
        )


@dataclass(frozen=True)
class LongitudinalBaselineReport:
    train_count: int
    test_count: int
    max_pick: int
    regular_model: FittedBaselineModel
    impact_model: FittedBaselineModel
    rows: list[dict[str, str]]
    summary: dict[str, str]


def build_longitudinal_baseline_report(
    labels_root: str | Path,
    class_root: str | Path,
    *,
    as_of_date: date,
    train_end_year: int = 2018,
    test_start_year: int = 2019,
    test_end_year: int | None = 2021,
    horizon_years: int = 5,
) -> LongitudinalBaselineReport:
    if train_end_year >= test_start_year:
        raise ValueError("train_end_year must be before test_start_year")
    if test_end_year is not None and test_end_year < test_start_year:
        raise ValueError("test_end_year must not be before test_start_year")
    examples = load_baseline_examples(
        labels_root, class_root, as_of_date=as_of_date, horizon_years=horizon_years
    )
    train = [example for example in examples if example.draft_year <= train_end_year]
    test = [
        example
        for example in examples
        if example.draft_year >= test_start_year
        and (test_end_year is None or example.draft_year <= test_end_year)
    ]
    if not train or not test:
        raise ValueError("temporal split requires both training and test examples")
    max_pick = max(example.overall_pick for example in train)
    regular_model = fit_logistic_baseline(train, max_pick=max_pick, target="regular_nhl")
    impact_model = fit_logistic_baseline(train, max_pick=max_pick, target="impact_nhl")
    rows = prediction_rows(test, max_pick, regular_model, impact_model)
    regular_actuals = [row["regular_nhl"] == "1" for row in rows]
    regular_scores = [float(row["regular_prediction"]) for row in rows]
    impact_actuals = [row["impact_nhl"] == "1" for row in rows]
    impact_scores = [float(row["impact_prediction"]) for row in rows]
    summary = {
        "as_of_date": as_of_date.isoformat(),
        "horizon_years": str(horizon_years),
        "train_draft_years": format_years(train),
        "test_draft_years": format_years(test),
        "train_players": str(len(train)),
        "test_players": str(len(test)),
        "slot_score_max_pick": str(max_pick),
        "regular_nhl_target": "100_or_more_nhl_games",
        "impact_player_target": "50_or_more_points_or_25_or_more_goalie_starts",
        "model": "l2_regularized_logistic_regression",
        "iterations": "800",
        "l2_penalty": "0.05",
        "regular_nhl_brier": f"{brier_score(regular_actuals, regular_scores):.4f}",
        "impact_nhl_brier": f"{brier_score(impact_actuals, impact_scores):.4f}",
        "regular_nhl_precision_at_25": (
            f"{precision_at_n(regular_actuals, regular_scores, 25):.4f}"
        ),
        "impact_nhl_precision_at_25": (f"{precision_at_n(impact_actuals, impact_scores, 25):.4f}"),
    }
    return LongitudinalBaselineReport(
        train_count=len(train),
        test_count=len(test),
        max_pick=max_pick,
        regular_model=regular_model,
        impact_model=impact_model,
        rows=rows,
        summary=summary,
    )


def load_baseline_examples(
    labels_root: str | Path,
    class_root: str | Path,
    *,
    as_of_date: date,
    horizon_years: int,
) -> list[BaselineExample]:
    labels_base = Path(labels_root)
    classes_base = Path(class_root)
    examples: list[BaselineExample] = []
    for labels_path in sorted(labels_base.glob(f"*/{horizon_years}y.csv")):
        labels = eligible_outcome_labels(load_outcome_labels(labels_path, as_of_date=as_of_date))
        if not labels:
            continue
        draft_years = {label.draft_year for label in labels}
        if len(draft_years) != 1:
            raise ValueError(f"labels must contain one draft year: {labels_path}")
        draft_year = next(iter(draft_years))
        selections = load_csv_by_id(
            classes_base / str(draft_year) / "final" / "draft_selections.csv"
        )
        players = load_csv_by_id(classes_base / str(draft_year) / "final" / "players.csv")
        for label in labels:
            if label.horizon_years != horizon_years:
                continue
            examples.append(build_example(label, selections, players, labels_path))
    if not examples:
        raise ValueError(f"no mature {horizon_years}-year outcome labels found under {labels_base}")
    return examples


def load_csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    mapped = {
        row.get("player_id", "").strip(): row for row in rows if row.get("player_id", "").strip()
    }
    if len(mapped) != len(rows):
        raise ValueError(f"invalid or duplicate player IDs: {path}")
    return mapped


def build_example(
    label: OutcomeLabel,
    selections: dict[str, dict[str, str]],
    players: dict[str, dict[str, str]],
    labels_path: Path,
) -> BaselineExample:
    selection = selections.get(label.player_id)
    player = players.get(label.player_id)
    if selection is None or player is None:
        raise ValueError(f"missing normalized draft identity for {label.player_id}: {labels_path}")
    try:
        overall_pick = int(selection.get("overall_pick", ""))
    except ValueError as exc:
        raise ValueError(f"invalid overall pick for {label.player_id}") from exc
    if overall_pick <= 0:
        raise ValueError(f"invalid overall pick for {label.player_id}")
    position = player.get("position", "").strip().upper()
    if position not in {"C", "L", "R", "LW", "RW", "F", "C/LW", "C/RW", "LW/RW", "D", "G"}:
        raise ValueError(f"unsupported position for {label.player_id}: {position}")
    return BaselineExample(
        player_id=label.player_id,
        draft_year=label.draft_year,
        overall_pick=overall_pick,
        position=position,
        nhl_games=label.nhl_games,
        nhl_points=label.nhl_points,
        goalie_starts=label.goalie_starts,
    )


def fit_logistic_baseline(
    examples: list[BaselineExample], *, max_pick: int, target: str
) -> FittedBaselineModel:
    actuals = [target_value(example, target) for example in examples]
    positive_rate = sum(actuals) / len(actuals)
    if positive_rate in {0.0, 1.0}:
        return FittedBaselineModel(target, 0.0, (0.0,) * len(FEATURE_NAMES), positive_rate)
    weights = [0.0] * len(FEATURE_NAMES)
    intercept = math.log(positive_rate / (1.0 - positive_rate))
    learning_rate = 0.2
    l2_penalty = 0.05
    feature_rows = [example.features(max_pick) for example in examples]
    for _ in range(800):
        errors = [
            sigmoid(intercept + sum(weight * value for weight, value in zip(weights, features)))
            - actual
            for features, actual in zip(feature_rows, actuals)
        ]
        intercept -= learning_rate * sum(errors) / len(errors)
        for index in range(len(weights)):
            gradient = sum(
                error * features[index] for error, features in zip(errors, feature_rows)
            ) / len(errors)
            weights[index] -= learning_rate * (gradient + l2_penalty * weights[index])
    return FittedBaselineModel(target, intercept, tuple(weights), None)


def target_value(example: BaselineExample, target: str) -> float:
    if target == "regular_nhl":
        return float(example.is_regular_nhler)
    if target == "impact_nhl":
        return float(example.is_impact_player)
    raise ValueError(f"unsupported target: {target}")


def format_years(examples: list[BaselineExample]) -> str:
    return ",".join(str(year) for year in sorted({example.draft_year for example in examples}))


def prediction_rows(
    examples: list[BaselineExample],
    max_pick: int,
    regular_model: FittedBaselineModel,
    impact_model: FittedBaselineModel,
) -> list[dict[str, str]]:
    rows = []
    for example in sorted(examples, key=lambda item: (item.draft_year, item.overall_pick)):
        features = example.features(max_pick)
        regular_prediction = regular_model.predict(features)
        impact_prediction = impact_model.predict(features)
        rows.append(
            {
                "player_id": example.player_id,
                "draft_year": str(example.draft_year),
                "overall_pick": str(example.overall_pick),
                "position": example.position,
                "role": example.role,
                "regular_nhl": str(int(example.is_regular_nhler)),
                "impact_nhl": str(int(example.is_impact_player)),
                "nhl_games": str(example.nhl_games),
                "nhl_points": str(example.nhl_points),
                "goalie_starts": str(example.goalie_starts),
                "regular_prediction": f"{regular_prediction:.6f}",
                "impact_prediction": f"{impact_prediction:.6f}",
            }
        )
    return rows


def write_longitudinal_baseline_report(
    labels_root: str | Path,
    class_root: str | Path,
    output_dir: str | Path,
    *,
    as_of_date: date,
    train_end_year: int = 2018,
    test_start_year: int = 2019,
    test_end_year: int | None = 2021,
    horizon_years: int = 5,
) -> LongitudinalBaselineReport:
    report = build_longitudinal_baseline_report(
        labels_root,
        class_root,
        as_of_date=as_of_date,
        train_end_year=train_end_year,
        test_start_year=test_start_year,
        test_end_year=test_end_year,
        horizon_years=horizon_years,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "predictions.csv", report.rows)
    write_csv(root / "summary.csv", [report.summary])
    write_csv(root / "model_coefficients.csv", coefficient_rows(report))
    (root / "summary.md").write_text(format_report(report), encoding="utf-8")
    return report


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0]) if rows else ["player_id"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def coefficient_rows(report: LongitudinalBaselineReport) -> list[dict[str, str]]:
    rows = []
    for model in (report.regular_model, report.impact_model):
        rows.append(
            {
                "target": model.target,
                "feature": "intercept",
                "weight": f"{model.intercept:.6f}",
                "constant_probability": ""
                if model.constant_probability is None
                else f"{model.constant_probability:.6f}",
                "slot_score_max_pick": str(report.max_pick),
                "as_of_date": report.summary["as_of_date"],
            }
        )
        rows.extend(
            {
                "target": model.target,
                "feature": feature,
                "weight": f"{weight:.6f}",
                "constant_probability": "",
                "slot_score_max_pick": str(report.max_pick),
                "as_of_date": report.summary["as_of_date"],
            }
            for feature, weight in zip(FEATURE_NAMES, model.weights)
        )
    return rows


def format_report(report: LongitudinalBaselineReport) -> str:
    summary = report.summary
    return "\n".join(
        [
            "# Temporal Slot-and-Role Baseline",
            "",
            f"- Target horizon: {summary['horizon_years']} years",
            f"- As-of date: {summary['as_of_date']}",
            f"- Training: {summary['train_draft_years']} ({summary['train_players']} players)",
            f"- Held out: {summary['test_draft_years']} ({summary['test_players']} players)",
            f"- Slot-score normalization: training maximum pick {summary['slot_score_max_pick']}",
            f"- Regular-NHL Brier: {summary['regular_nhl_brier']}",
            f"- Impact-player Brier: {summary['impact_nhl_brier']}",
            f"- Regular-NHL Precision@25: {summary['regular_nhl_precision_at_25']}",
            f"- Impact-player Precision@25: {summary['impact_nhl_precision_at_25']}",
            "",
            "Targets: regular NHLer = at least 100 NHL games; impact player = at least "
            "50 points for skaters or 25 starts for goalies.",
            "Features are official draft slot and position only (forward is the reference role). "
            "This is a transparent probability comparator, not a player-value estimate or evidence "
            "of lift over consensus or production features.",
            "",
        ]
    )


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, value))))
