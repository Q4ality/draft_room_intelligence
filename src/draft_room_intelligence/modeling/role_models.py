"""Simple pure-Python role-specific fitted models."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.evaluation.baselines import (
    evaluate_board_order,
    evaluate_historical_scores,
)
from draft_room_intelligence.modeling.feature_table import (
    FEATURE_COLUMNS,
    MODEL_FEATURE_COLUMNS,
    FeatureRow,
    build_feature_rows,
    role_group,
)
from draft_room_intelligence.domain import HistoricalProspect


@dataclass(frozen=True)
class FittedBinaryModel:
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float
    constant_probability: float | None = None

    def predict_probability(self, row: dict[str, str]) -> float:
        if self.constant_probability is not None:
            return self.constant_probability
        total = self.intercept
        for index, feature_name in enumerate(self.feature_names):
            value = float(row[feature_name])
            scale = self.scales[index] or 1.0
            standardized = (value - self.means[index]) / scale
            total += standardized * self.weights[index]
        return sigmoid(total)


@dataclass(frozen=True)
class RoleSpecificModels:
    nhler_models: dict[str, FittedBinaryModel]
    impact_models: dict[str, FittedBinaryModel]


def fit_role_specific_models(feature_rows: list[FeatureRow]) -> RoleSpecificModels:
    grouped = group_feature_rows_by_role(feature_rows)
    nhler_models: dict[str, FittedBinaryModel] = {}
    impact_models: dict[str, FittedBinaryModel] = {}
    for role, rows in grouped.items():
        nhler_models[role] = fit_binary_model(rows, target_column="is_nhler")
        impact_models[role] = fit_binary_model(rows, target_column="is_impact_player")
    return RoleSpecificModels(nhler_models=nhler_models, impact_models=impact_models)


def score_role_specific_models(
    models: RoleSpecificModels,
    feature_rows: list[FeatureRow],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for row in feature_rows:
        values = row.to_dict()
        role = values["role_group"]
        nhler_probability = models.nhler_models[role].predict_probability(values)
        impact_probability = models.impact_models[role].predict_probability(values)
        scores[values["player_id"]] = max(0.0, min(1.0, nhler_probability * 0.7 + impact_probability * 0.3))
    return scores


def evaluate_role_specific_models(
    prospects: list[HistoricalProspect],
    *,
    precision_n: int = 25,
) -> tuple[
    list[FeatureRow],
    RoleSpecificModels,
    dict[str, float],
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
]:
    feature_rows = build_feature_rows(prospects)
    models = fit_role_specific_models(feature_rows)
    scores = cross_validated_role_specific_scores(feature_rows, folds=5)
    probability_report = evaluate_historical_scores(prospects, scores, precision_n=precision_n)
    board_report = evaluate_board_order(prospects, scores, top_ns=(10, precision_n, 50))
    return feature_rows, models, scores, probability_report, board_report


def write_model_summary(path: str | Path, models: RoleSpecificModels) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["target", "role_group", "intercept", "constant_probability", "feature_names", "weights"],
        )
        writer.writeheader()
        for target_name, model_map in (("nhler", models.nhler_models), ("impact", models.impact_models)):
            for role, model in sorted(model_map.items()):
                writer.writerow(
                    {
                        "target": target_name,
                        "role_group": role,
                        "intercept": f"{model.intercept:.6f}",
                        "constant_probability": (
                            f"{model.constant_probability:.6f}" if model.constant_probability is not None else ""
                        ),
                        "feature_names": "|".join(model.feature_names),
                        "weights": "|".join(f"{weight:.6f}" for weight in model.weights),
                    }
                )


def fit_binary_model(rows: list[FeatureRow], *, target_column: str) -> FittedBinaryModel:
    feature_names = tuple(MODEL_FEATURE_COLUMNS)
    x_rows = [[float(row.to_dict()[feature]) for feature in feature_names] for row in rows]
    y_values = [float(row.to_dict()[target_column]) for row in rows]
    positive_rate = sum(y_values) / len(y_values) if y_values else 0.0
    if positive_rate in {0.0, 1.0}:
        return FittedBinaryModel(
            feature_names=feature_names,
            means=tuple(0.0 for _ in feature_names),
            scales=tuple(1.0 for _ in feature_names),
            weights=tuple(0.0 for _ in feature_names),
            intercept=0.0,
            constant_probability=positive_rate,
        )

    means = tuple(sum(row[index] for row in x_rows) / len(x_rows) for index in range(len(feature_names)))
    scales = []
    standardized_rows: list[list[float]] = []
    for index in range(len(feature_names)):
        variance = sum((row[index] - means[index]) ** 2 for row in x_rows) / len(x_rows)
        scale = math.sqrt(variance) or 1.0
        scales.append(scale)
    for row in x_rows:
        standardized_rows.append([(row[index] - means[index]) / scales[index] for index in range(len(feature_names))])

    weights = [0.0] * len(feature_names)
    intercept = math.log(positive_rate / (1.0 - positive_rate))
    learning_rate = 0.08
    l2_penalty = 0.01

    for _ in range(600):
        gradient = [0.0] * len(feature_names)
        intercept_gradient = 0.0
        for features, actual in zip(standardized_rows, y_values):
            prediction = sigmoid(intercept + sum(weight * value for weight, value in zip(weights, features)))
            error = prediction - actual
            intercept_gradient += error
            for index, value in enumerate(features):
                gradient[index] += error * value
        intercept -= learning_rate * intercept_gradient / len(standardized_rows)
        for index in range(len(weights)):
            penalty = l2_penalty * weights[index]
            weights[index] -= learning_rate * ((gradient[index] / len(standardized_rows)) + penalty)

    return FittedBinaryModel(
        feature_names=feature_names,
        means=means,
        scales=tuple(scales),
        weights=tuple(weights),
        intercept=intercept,
        constant_probability=None,
    )


def group_feature_rows_by_role(feature_rows: list[FeatureRow]) -> dict[str, list[FeatureRow]]:
    grouped: dict[str, list[FeatureRow]] = {}
    for row in feature_rows:
        grouped.setdefault(row.to_dict()["role_group"], []).append(row)
    return grouped


def cross_validated_role_specific_scores(
    feature_rows: list[FeatureRow],
    *,
    folds: int,
) -> dict[str, float]:
    grouped = group_feature_rows_by_role(feature_rows)
    scores: dict[str, float] = {}
    for rows in grouped.values():
        ordered_rows = sorted(rows, key=lambda row: row.to_dict()["player_id"])
        fold_buckets = [[] for _ in range(folds)]
        for index, row in enumerate(ordered_rows):
            fold_buckets[index % folds].append(row)

        for fold_index in range(folds):
            holdout_rows = fold_buckets[fold_index]
            training_rows = [
                row
                for bucket_index, bucket in enumerate(fold_buckets)
                if bucket_index != fold_index
                for row in bucket
            ]
            if not training_rows:
                training_rows = holdout_rows
            models = fit_role_specific_models(training_rows)
            scores.update(score_role_specific_models(models, holdout_rows))
    return scores


def sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-value)
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)
