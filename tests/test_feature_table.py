from draft_room_intelligence.domain import HistoricalProspect, PreDraftStatLine
from draft_room_intelligence.modeling.feature_table import build_feature_rows


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
    assert row["adult_game_share"] == "0.294118"
    assert row["pro_game_share"] == "0.294118"
