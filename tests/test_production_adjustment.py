from draft_room_intelligence.domain import HistoricalProspect, PreDraftStatLine
from draft_room_intelligence.projection.production_adjustment import (
    LeagueContext,
    build_adjusted_production_features,
    role_group,
)


CONTEXTS = {
    "WHL": LeagueContext("WHL", "Canadian Junior", "junior", False, 1.0, 1.08),
    "SHL": LeagueContext("SHL", "Europe Pro", "elite", True, 1.2, 1.15),
    "Unknown": LeagueContext("Unknown", "Unknown", "unknown", False, 0.7, 1.0),
}


def prospect(
    player_id: str,
    position: str,
    league: str,
    games: int,
    goals: int,
    assists: int,
    *,
    pre_draft_stat_lines: tuple[PreDraftStatLine, ...] | None = None,
) -> HistoricalProspect:
    stat_line = PreDraftStatLine(
        league=league,
        team="Example",
        season="2018-19",
        games=games,
        goals=goals,
        assists=assists,
    )
    return HistoricalProspect(
        player_id=player_id,
        name=player_id,
        draft_year=2019,
        position=position,
        age_at_draft=18.0,
        height_cm=180,
        weight_kg=80,
        consensus_rank=1,
        stat_line=stat_line,
        pre_draft_stat_lines=pre_draft_stat_lines or (stat_line,),
    )


def test_role_group_maps_positions():
    assert role_group("C") == "forward"
    assert role_group("RW") == "forward"
    assert role_group("D") == "defense"
    assert role_group("RHD") == "defense"
    assert role_group("G") == "goalie"


def test_adjusted_production_ranks_top_5_within_league_role():
    prospects = [
        prospect("p1", "C", "WHL", 50, 20, 30),
        prospect("p2", "LW", "WHL", 50, 10, 20),
        prospect("p3", "D", "WHL", 50, 15, 20),
    ]

    features = build_adjusted_production_features(prospects, league_contexts=CONTEXTS)

    assert features["p1"].role_rank == 1
    assert features["p1"].is_top_5_role
    assert features["p2"].role_rank == 2
    assert features["p3"].role_group == "defense"
    assert features["p3"].role_rank == 1


def test_adult_league_weight_and_bonus_raise_adjusted_score():
    prospects = [
        prospect("junior", "C", "WHL", 40, 10, 10),
        prospect("adult", "C", "SHL", 40, 10, 10),
    ]

    features = build_adjusted_production_features(prospects, league_contexts=CONTEXTS)

    assert features["adult"].adult_league
    assert features["adult"].adult_league_bonus == 0.06
    assert features["adult"].adjusted_score > features["junior"].adjusted_score


def test_playoff_lines_and_aliases_raise_adjusted_score():
    playoff_line = PreDraftStatLine(
        league="Rus-MHL",
        team="Example",
        season="2018-19",
        games=10,
        goals=4,
        assists=6,
        regular_season=False,
    )
    regular_line = PreDraftStatLine(
        league="Rus-MHL",
        team="Example",
        season="2018-19",
        games=30,
        goals=10,
        assists=20,
    )
    comparison = prospect("regular", "C", "MHL", 40, 14, 26)
    boosted = prospect(
        "boosted",
        "C",
        "Rus-MHL",
        30,
        10,
        20,
        pre_draft_stat_lines=(regular_line, playoff_line),
    )

    features = build_adjusted_production_features([comparison, boosted], league_contexts=CONTEXTS)

    assert features["boosted"].playoff_bonus > 0.0
    assert features["boosted"].league == "Rus-MHL"
    assert features["boosted"].adjusted_score > features["regular"].adjusted_score
