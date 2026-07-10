"""Small dependency-free evaluation metrics."""

from __future__ import annotations


def brier_score(y_true: list[bool], y_score: list[float]) -> float:
    validate_same_length(y_true, y_score)
    if not y_true:
        raise ValueError("brier_score requires at least one observation")
    return sum((float(actual) - score) ** 2 for actual, score in zip(y_true, y_score)) / len(y_true)


def precision_at_n(y_true: list[bool], y_score: list[float], n: int) -> float:
    validate_same_length(y_true, y_score)
    if n <= 0:
        raise ValueError("n must be positive")
    if not y_true:
        raise ValueError("precision_at_n requires at least one observation")

    paired = sorted(zip(y_true, y_score), key=lambda item: item[1], reverse=True)
    selected = paired[: min(n, len(paired))]
    return sum(1 for actual, _ in selected if actual) / len(selected)


def spearman_rank_correlation(y_true: list[float], y_score: list[float]) -> float:
    validate_same_length(y_true, y_score)
    if len(y_true) < 2:
        raise ValueError("spearman_rank_correlation requires at least two observations")

    true_ranks = average_ranks(y_true)
    score_ranks = average_ranks(y_score)
    return pearson_correlation(true_ranks, score_ranks)


def average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0

    while index < len(indexed):
        start = index
        value = indexed[index][1]
        while index < len(indexed) and indexed[index][1] == value:
            index += 1

        average_rank = (start + 1 + index) / 2
        for original_index, _ in indexed[start:index]:
            ranks[original_index] = average_rank

    return ranks


def pearson_correlation(left: list[float], right: list[float]) -> float:
    validate_same_length(left, right)
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_denominator = sum((a - left_mean) ** 2 for a in left)
    right_denominator = sum((b - right_mean) ** 2 for b in right)

    if left_denominator == 0 or right_denominator == 0:
        return 0.0
    return numerator / (left_denominator * right_denominator) ** 0.5


def validate_same_length(left: list[object], right: list[object]) -> None:
    if len(left) != len(right):
        raise ValueError("inputs must have the same length")
