import csv

import pytest

from draft_room_intelligence.domain import HistoricalProspect, PreDraftStatLine
from draft_room_intelligence.modeling.feature_table import (
    build_feature_rows,
    load_advanced_stat_summaries,
)


def test_build_feature_rows_includes_pre_draft_context_shares():
    regular = PreDraftStatLine(
        league="NCHC",
        team="Denver",
        season="2018-19",
        games=20,
        goals=6,
        assists=10,
    )
    playoff = PreDraftStatLine(
        league="NCHC",
        team="Denver",
        season="2018-19",
        games=4,
        goals=1,
        assists=3,
        regular_season=False,
    )
    pro = PreDraftStatLine(
        league="SHL",
        team="Frolunda",
        season="2018-19",
        games=10,
        goals=1,
        assists=2,
    )
    prospect = HistoricalProspect(
        player_id="p1",
        name="Example Prospect",
        draft_year=2019,
        position="C",
        age_at_draft=18.2,
        height_cm=183,
        weight_kg=82,
        consensus_rank=12,
        stat_line=regular,
        handedness="L",
        pre_draft_stat_lines=(regular, playoff, pro),
    )

    row = build_feature_rows([prospect])[0].to_dict()

    assert row["primary_league"] == "NCAA"
    assert row["primary_league_family"] == "College"
    assert row["primary_competition_level"] == "high"
    assert row["pre_draft_regular_season_games"] == "30"
    assert row["pre_draft_playoff_games"] == "4"
    assert row["college_game_share"] == "0.705882"
    assert row["adult_games"] == "10"
    assert row["adult_sample_tier"] == "meaningful"
    assert row["adult_evidence_weight"] == "0.620000"
    assert row["meaningful_adult_sample"] == "1"
    assert row["adult_game_share"] == "0.294118"
    assert row["pro_game_share"] == "0.294118"
    assert row["meaningful_playoff_sample"] == "0"


def test_build_feature_rows_uses_league_exposure_when_games_are_missing():
    adult_source_league = PreDraftStatLine(
        league="SweHL",
        team="Djurgarden",
        season="2024-25",
        games=0,
        goals=0,
        assists=0,
    )
    prospect = HistoricalProspect(
        player_id="p2",
        name="Thin Source Prospect",
        draft_year=2025,
        position="D",
        age_at_draft=18.0,
        height_cm=0,
        weight_kg=0,
        consensus_rank=3,
        stat_line=adult_source_league,
        pre_draft_stat_lines=(adult_source_league,),
    )

    row = build_feature_rows([prospect])[0].to_dict()

    assert row["pre_draft_total_games"] == "0"
    assert row["primary_league"] == "SHL"
    assert row["primary_league_family"] == "Europe Pro"
    assert row["primary_competition_level"] == "elite"
    assert row["adult_game_share"] == "1.000000"
    assert row["adult_sample_tier"] == "none"
    assert row["adult_evidence_weight"] == "0.000000"
    assert row["meaningful_adult_sample"] == "0"
    assert row["pro_game_share"] == "1.000000"
    assert row["average_league_weight"] == "1.200000"
    assert row["adjusted_production_score"] == "0.000000"


def test_build_feature_rows_includes_goalie_metrics():
    goalie_line = PreDraftStatLine(
        league="OHL",
        team="Owen Sound",
        season="2024-25",
        games=47,
        goals=0,
        assists=0,
        points=0,
        goalie_minutes=2705.0,
        shots_against=1665,
        saves=1514,
        goals_against=151,
        save_percentage=0.909,
        goals_against_average=3.35,
        wins=17,
        losses=22,
        ties=3,
        shutouts=0,
    )
    prospect = HistoricalProspect(
        player_id="g1",
        name="Example Goalie",
        draft_year=2025,
        position="G",
        age_at_draft=18.3,
        height_cm=190,
        weight_kg=86,
        consensus_rank=30,
        stat_line=goalie_line,
        handedness="L",
        pre_draft_stat_lines=(goalie_line,),
    )

    row = build_feature_rows([prospect])[0].to_dict()

    assert row["is_goalie"] == "1"
    assert row["goalie_games"] == "47"
    assert row["goalie_minutes"] == "2705.00"
    assert row["goalie_shots_against"] == "1665"
    assert row["goalie_saves"] == "1514"
    assert row["goalie_save_percentage"] == "0.909309"
    assert row["goalie_goals_against_average"] == "3.349353"
    assert float(row["goalie_quality_score"]) > 0.0


def test_build_feature_rows_uses_sample_weighted_role_advanced_stats(tmp_path):
    advanced_path = tmp_path / "advanced_stat_lines.csv"
    with advanced_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "player_id",
                "timing",
                "games",
                "plus_minus",
                "shots",
                "blocks",
                "faceoff_wins",
                "faceoff_losses",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "player_id": "d1",
                "timing": "pre_draft",
                "games": "10",
                "plus_minus": "5",
                "shots": "20",
                "blocks": "15",
                "faceoff_wins": "0",
                "faceoff_losses": "0",
            }
        )

    stat_line = PreDraftStatLine(
        league="NCAA",
        team="Example",
        season="2024-25",
        games=10,
        goals=2,
        assists=5,
    )
    prospect = HistoricalProspect(
        player_id="d1",
        name="Example Defense",
        draft_year=2025,
        position="D",
        age_at_draft=18.2,
        height_cm=188,
        weight_kg=84,
        consensus_rank=15,
        stat_line=stat_line,
    )

    summaries = load_advanced_stat_summaries(tmp_path)
    row = build_feature_rows([prospect], summaries)[0].to_dict()

    assert row["advanced_games"] == "10"
    assert row["advanced_sample_weight"] == "0.500000"
    assert row["plus_minus_per_game"] == "0.500000"
    assert row["shots_per_game"] == "2.000000"
    assert row["blocks_per_game"] == "1.500000"
    assert 0.0 < float(row["advanced_role_score"]) < 0.5


def test_advanced_stat_loader_rejects_schema_drift(tmp_path):
    (tmp_path / "advanced_stat_lines.csv").write_text(
        "player_id,games\np1,10\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema v1 missing columns"):
        load_advanced_stat_summaries(tmp_path)
