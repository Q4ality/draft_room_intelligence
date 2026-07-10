"""Baseline scoring functions for historical backtests."""

from __future__ import annotations

from draft_room_intelligence.domain import HistoricalProspect, Projection
from draft_room_intelligence.evaluation.metrics import (
    brier_score,
    precision_at_n,
    spearman_rank_correlation,
)
from draft_room_intelligence.projection.production_adjustment import (
    AdjustedProduction,
    build_adjusted_production_features,
)


def consensus_probability(prospect: HistoricalProspect, max_rank: int | None = None) -> float:
    rank_ceiling = max_rank or max(100, prospect.consensus_rank)
    if rank_ceiling <= 1:
        return 1.0
    return clamp(1.0 - ((prospect.consensus_rank - 1) / (rank_ceiling - 1)))


def draft_slot_probability(prospect: HistoricalProspect, max_pick: int = 224) -> float:
    if prospect.draft_slot is None:
        return 0.0
    if max_pick <= 1:
        return 1.0
    return clamp(1.0 - ((prospect.draft_slot - 1) / (max_pick - 1)))


def production_score(prospect: HistoricalProspect, ceiling_ppg: float = 1.5) -> float:
    if ceiling_ppg <= 0:
        raise ValueError("ceiling_ppg must be positive")
    return clamp(prospect.stat_line.points_per_game / ceiling_ppg)


def evaluate_binary_target(
    actuals: list[bool],
    scores: list[float],
    *,
    precision_n: int = 10,
) -> dict[str, float]:
    return {
        "count": float(len(actuals)),
        "positive_rate": sum(1 for actual in actuals if actual) / len(actuals),
        "brier_score": brier_score(actuals, scores),
        "precision_at_n": precision_at_n(actuals, scores, precision_n),
    }


def evaluate_historical_scores(
    prospects: list[HistoricalProspect],
    scores: dict[str, float],
    *,
    precision_n: int = 10,
) -> dict[str, dict[str, float]]:
    evaluable = [prospect for prospect in prospects if prospect.outcome is not None]
    if not evaluable:
        raise ValueError("at least one prospect with DraftOutcome is required")

    missing_scores = [prospect.player_id for prospect in evaluable if prospect.player_id not in scores]
    if missing_scores:
        joined = ", ".join(missing_scores)
        raise ValueError(f"missing scores for player ids: {joined}")

    ordered_scores = [scores[prospect.player_id] for prospect in evaluable]
    nhler_actuals = [prospect.outcome.is_nhler for prospect in evaluable if prospect.outcome]
    impact_actuals = [prospect.outcome.is_impact_player for prospect in evaluable if prospect.outcome]
    bust_actuals = [prospect.outcome.is_bust for prospect in evaluable if prospect.outcome]
    games_played = [float(prospect.outcome.nhl_games) for prospect in evaluable if prospect.outcome]

    return {
        "nhler": evaluate_binary_target(nhler_actuals, ordered_scores, precision_n=precision_n),
        "impact": evaluate_binary_target(impact_actuals, ordered_scores, precision_n=precision_n),
        "bust": evaluate_binary_target(
            bust_actuals,
            [1.0 - score for score in ordered_scores],
            precision_n=precision_n,
        ),
        "rank": {
            "count": float(len(evaluable)),
            "spearman_nhl_games": spearman_rank_correlation(games_played, ordered_scores),
        },
    }


def evaluate_board_order(
    prospects: list[HistoricalProspect],
    scores: dict[str, float],
    *,
    top_ns: tuple[int, ...] = (10, 25, 50),
) -> dict[str, dict[str, float]]:
    evaluable = [prospect for prospect in prospects if prospect.outcome is not None]
    if not evaluable:
        raise ValueError("at least one prospect with DraftOutcome is required")

    missing_scores = [prospect.player_id for prospect in evaluable if prospect.player_id not in scores]
    if missing_scores:
        joined = ", ".join(missing_scores)
        raise ValueError(f"missing scores for player ids: {joined}")

    ordered = sorted(
        evaluable,
        key=lambda prospect: scores[prospect.player_id],
        reverse=True,
    )
    overall_avg_games = sum(prospect.outcome.nhl_games for prospect in ordered if prospect.outcome) / len(ordered)
    overall_avg_points = sum(prospect.outcome.nhl_points for prospect in ordered if prospect.outcome) / len(ordered)

    report: dict[str, dict[str, float]] = {}
    for top_n in top_ns:
        selected = ordered[: min(top_n, len(ordered))]
        if not selected:
            continue
        avg_games = sum(prospect.outcome.nhl_games for prospect in selected if prospect.outcome) / len(selected)
        avg_points = sum(prospect.outcome.nhl_points for prospect in selected if prospect.outcome) / len(selected)
        nhlers = sum(1 for prospect in selected if prospect.outcome and prospect.outcome.is_nhler)
        impacts = sum(1 for prospect in selected if prospect.outcome and prospect.outcome.is_impact_player)
        busts = sum(1 for prospect in selected if prospect.outcome and prospect.outcome.is_bust)
        report[f"top_{top_n}"] = {
            "count": float(len(selected)),
            "avg_nhl_games": avg_games,
            "avg_nhl_points": avg_points,
            "nhlers": float(nhlers),
            "impact_players": float(impacts),
            "busts": float(busts),
            "games_lift": (avg_games / overall_avg_games) if overall_avg_games else 0.0,
            "points_lift": (avg_points / overall_avg_points) if overall_avg_points else 0.0,
        }
    return report


def consensus_scores(prospects: list[HistoricalProspect]) -> dict[str, float]:
    max_rank = max((prospect.consensus_rank for prospect in prospects), default=100)
    return {
        prospect.player_id: consensus_probability(prospect, max_rank=max_rank)
        for prospect in prospects
    }


def projection_scores(projections: dict[str, Projection]) -> dict[str, float]:
    return {
        player_id: projection.nhl_probability
        for player_id, projection in projections.items()
    }


def adjusted_production_scores(prospects: list[HistoricalProspect]) -> dict[str, float]:
    features = build_adjusted_production_features(prospects)
    max_score = max((feature.adjusted_score for feature in features.values()), default=0.0)
    if max_score <= 0:
        return {prospect.player_id: 0.0 for prospect in prospects}

    return {
        prospect.player_id: clamp(features[prospect.player_id].adjusted_score / max_score)
        if prospect.player_id in features
        else 0.0
        for prospect in prospects
    }


def contextual_scores(prospects: list[HistoricalProspect]) -> dict[str, float]:
    adjusted_features = build_adjusted_production_features(prospects)
    production_scores = adjusted_production_scores(prospects)
    max_rank = max((prospect.consensus_rank for prospect in prospects), default=100)

    return {
        prospect.player_id: clamp(
            (
                production_component(prospect, adjusted_features, production_scores) * 0.36
                + consensus_probability(prospect, max_rank=max_rank) * 0.28
                + age_component(prospect) * 0.10
                + size_component(prospect) * 0.08
                + handedness_component(prospect) * 0.05
                + position_component(prospect) * 0.05
                + sample_component(prospect, adjusted_features) * 0.08
            )
        )
        for prospect in prospects
    }


def role_aware_scores(prospects: list[HistoricalProspect]) -> dict[str, float]:
    adjusted_features = build_adjusted_production_features(prospects)
    production_scores = adjusted_production_scores(prospects)
    max_rank = max((prospect.consensus_rank for prospect in prospects), default=100)

    return {
        prospect.player_id: clamp(
            role_group_score(
                prospect,
                adjusted_features,
                production_scores,
                consensus_probability(prospect, max_rank=max_rank),
            )
        )
        for prospect in prospects
    }


def role_specific_hybrid_scores(prospects: list[HistoricalProspect]) -> dict[str, float]:
    adjusted_features = build_adjusted_production_features(prospects)
    production_scores = adjusted_production_scores(prospects)
    contextual = contextual_scores(prospects)
    max_rank = max((prospect.consensus_rank for prospect in prospects), default=100)

    return {
        prospect.player_id: clamp(
            role_specific_hybrid_score(
                prospect,
                adjusted_features=adjusted_features,
                production_scores=production_scores,
                contextual_score=contextual[prospect.player_id],
                consensus_score=consensus_probability(prospect, max_rank=max_rank),
            )
        )
        for prospect in prospects
    }


def weighted_hybrid_scores(
    score_sets: list[tuple[dict[str, float], float]],
) -> dict[str, float]:
    if not score_sets:
        raise ValueError("at least one score set is required")
    total_weight = sum(weight for _, weight in score_sets)
    if total_weight <= 0:
        raise ValueError("total score weight must be positive")

    player_ids = set(score_sets[0][0])
    for scores, _ in score_sets[1:]:
        player_ids &= set(scores)

    return {
        player_id: clamp(
            sum(scores[player_id] * weight for scores, weight in score_sets) / total_weight
        )
        for player_id in player_ids
    }


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def production_component(
    prospect: HistoricalProspect,
    adjusted_features: dict[str, AdjustedProduction],
    production_scores: dict[str, float],
) -> float:
    if prospect.player_id in production_scores:
        return production_scores[prospect.player_id]
    return consensus_probability(prospect)


def age_component(prospect: HistoricalProspect) -> float:
    return clamp((18.9 - prospect.age_at_draft) / 1.4)


def size_component(prospect: HistoricalProspect) -> float:
    if prospect.position == "G":
        return clamp((prospect.height_cm - 180) / 20) * 0.8 + clamp((prospect.weight_kg - 75) / 20) * 0.2
    if prospect.position == "D":
        return clamp((prospect.height_cm - 178) / 18) * 0.7 + clamp((prospect.weight_kg - 72) / 22) * 0.3
    return clamp((prospect.height_cm - 172) / 18) * 0.65 + clamp((prospect.weight_kg - 68) / 20) * 0.35


def handedness_component(prospect: HistoricalProspect) -> float:
    if prospect.position == "D" and prospect.handedness == "R":
        return 1.0
    if prospect.position == "G" and prospect.handedness:
        return 0.55
    if prospect.handedness:
        return 0.5
    return 0.35


def position_component(prospect: HistoricalProspect) -> float:
    premiums = {
        "C": 1.0,
        "D": 0.88,
        "RW": 0.72,
        "LW": 0.7,
        "F": 0.68,
        "G": 0.5,
    }
    return premiums.get(prospect.position, 0.65)


def sample_component(
    prospect: HistoricalProspect,
    adjusted_features: dict[str, AdjustedProduction],
) -> float:
    feature = adjusted_features.get(prospect.player_id)
    total_games = feature.games if feature is not None else prospect.stat_line.games
    games_score = clamp(total_games / 55)
    adult_bonus = 0.12 if feature and feature.adult_league else 0.0
    playoff_bonus = min(feature.playoff_bonus, 0.08) if feature else 0.0
    return clamp(games_score * 0.8 + adult_bonus + playoff_bonus)


def multi_row_component(prospect: HistoricalProspect) -> float:
    stat_lines = prospect.pre_draft_stat_lines or (prospect.stat_line,)
    if len(stat_lines) <= 1:
        return 0.35
    total_games = sum(line.games for line in stat_lines)
    distinct_leagues = len({line.league for line in stat_lines})
    playoff_rows = sum(1 for line in stat_lines if not line.regular_season)
    return clamp(
        0.35
        + min(total_games, 80) / 200
        + min(distinct_leagues, 3) * 0.08
        + playoff_rows * 0.06
    )


def goalie_component(
    prospect: HistoricalProspect,
    adjusted_features: dict[str, AdjustedProduction],
    consensus_score: float,
) -> float:
    size = size_component(prospect)
    sample = sample_component(prospect, adjusted_features)
    multi_row = multi_row_component(prospect)
    handed = handedness_component(prospect)
    age = age_component(prospect)
    draft_slot = draft_slot_component(prospect)
    return clamp(
        consensus_score * 0.42
        + size * 0.18
        + sample * 0.12
        + multi_row * 0.10
        + age * 0.08
        + draft_slot * 0.06
        + handed * 0.04
    )


def role_group_score(
    prospect: HistoricalProspect,
    adjusted_features: dict[str, AdjustedProduction],
    production_scores: dict[str, float],
    consensus_score: float,
) -> float:
    role = role_group(prospect)
    if role == "forward":
        return (
            production_component(prospect, adjusted_features, production_scores) * 0.40
            + consensus_score * 0.24
            + age_component(prospect) * 0.10
            + sample_component(prospect, adjusted_features) * 0.12
            + multi_row_component(prospect) * 0.07
            + size_component(prospect) * 0.07
            + handedness_component(prospect) * 0.03
            + position_component(prospect) * 0.03
        )
    if role == "defense":
        return (
            production_component(prospect, adjusted_features, production_scores) * 0.28
            + consensus_score * 0.26
            + age_component(prospect) * 0.08
            + sample_component(prospect, adjusted_features) * 0.11
            + multi_row_component(prospect) * 0.05
            + size_component(prospect) * 0.15
            + handedness_component(prospect) * 0.07
            + position_component(prospect) * 0.05
        )
    return goalie_component(prospect, adjusted_features, consensus_score)


def role_group(prospect: HistoricalProspect) -> str:
    if prospect.position == "G":
        return "goalie"
    if prospect.position == "D" or prospect.position.endswith("HD"):
        return "defense"
    return "forward"


def draft_slot_component(prospect: HistoricalProspect) -> float:
    return draft_slot_probability(prospect) if prospect.draft_slot is not None else 0.0


def role_specific_hybrid_score(
    prospect: HistoricalProspect,
    *,
    adjusted_features: dict[str, AdjustedProduction],
    production_scores: dict[str, float],
    contextual_score: float,
    consensus_score: float,
) -> float:
    role = role_group(prospect)
    if role == "forward":
        return (
            consensus_score * 0.34
            + production_component(prospect, adjusted_features, production_scores) * 0.26
            + contextual_score * 0.22
            + multi_row_component(prospect) * 0.10
            + sample_component(prospect, adjusted_features) * 0.08
        )
    if role == "defense":
        return (
            consensus_score * 0.30
            + production_component(prospect, adjusted_features, production_scores) * 0.20
            + contextual_score * 0.25
            + size_component(prospect) * 0.10
            + handedness_component(prospect) * 0.07
            + sample_component(prospect, adjusted_features) * 0.08
        )
    return (
        consensus_score * 0.45
        + goalie_component(prospect, adjusted_features, consensus_score) * 0.35
        + sample_component(prospect, adjusted_features) * 0.10
        + multi_row_component(prospect) * 0.10
    )
