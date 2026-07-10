from pathlib import Path

from draft_room_intelligence.data.historical_csv import load_historical_prospects_csv
from draft_room_intelligence.data.normalized_tables import load_normalized_historical_prospects
from draft_room_intelligence.evaluation.baselines import (
    adjusted_production_scores,
    consensus_scores,
    contextual_scores,
    draft_slot_probability,
    evaluate_historical_scores,
    production_score,
    role_aware_scores,
    role_specific_hybrid_scores,
    weighted_hybrid_scores,
)


FIXTURE = Path(__file__).parent / "fixtures" / "historical_prospects.csv"
PILOT = Path(__file__).parents[1] / "data" / "processed" / "pilot_2019"


def test_consensus_scores_and_historical_evaluation():
    prospects = load_historical_prospects_csv(FIXTURE)
    scores = consensus_scores(prospects)

    report = evaluate_historical_scores(prospects, scores, precision_n=1)

    assert scores["p2019-001"] > scores["p2019-002"]
    assert report["nhler"]["count"] == 2.0
    assert report["nhler"]["precision_at_n"] == 1.0
    assert report["impact"]["positive_rate"] == 0.5
    assert report["bust"]["precision_at_n"] == 1.0
    assert report["rank"]["spearman_nhl_games"] == 1.0


def test_draft_slot_and_production_scores_are_normalized():
    prospects = load_historical_prospects_csv(FIXTURE)

    assert draft_slot_probability(prospects[0]) > draft_slot_probability(prospects[1])
    assert 0.0 <= production_score(prospects[0]) <= 1.0


def test_adjusted_production_scores_cover_full_pilot_sample():
    prospects = load_normalized_historical_prospects(PILOT)
    scores = adjusted_production_scores(prospects)

    assert set(scores) == {prospect.player_id for prospect in prospects}
    assert max(scores.values()) == 1.0
    assert all(0.0 <= score <= 1.0 for score in scores.values())
    assert scores["2019-005-alex-turcotte"] > scores["2019-001-jack-hughes"]


def test_weighted_hybrid_scores_blend_common_player_ids():
    scores = weighted_hybrid_scores(
        [
            ({"p1": 1.0, "p2": 0.0}, 0.75),
            ({"p1": 0.0, "p2": 1.0}, 0.25),
        ]
    )

    assert scores == {"p1": 0.75, "p2": 0.25}


def test_contextual_scores_cover_full_pilot_sample():
    prospects = load_normalized_historical_prospects(PILOT)
    scores = contextual_scores(prospects)

    assert set(scores) == {prospect.player_id for prospect in prospects}
    assert all(0.0 <= score <= 1.0 for score in scores.values())
    assert scores["2019-001-jack-hughes"] > scores["2019-199-matthew-stienburg"]


def test_role_aware_scores_cover_full_pilot_sample():
    prospects = load_normalized_historical_prospects(PILOT)
    scores = role_aware_scores(prospects)

    assert set(scores) == {prospect.player_id for prospect in prospects}
    assert all(0.0 <= score <= 1.0 for score in scores.values())
    assert scores["2019-001-jack-hughes"] > scores["2019-199-matthew-stienburg"]


def test_role_specific_hybrid_scores_cover_full_pilot_sample():
    prospects = load_normalized_historical_prospects(PILOT)
    scores = role_specific_hybrid_scores(prospects)

    assert set(scores) == {prospect.player_id for prospect in prospects}
    assert all(0.0 <= score <= 1.0 for score in scores.values())
    assert scores["2019-001-jack-hughes"] > scores["2019-199-matthew-stienburg"]
