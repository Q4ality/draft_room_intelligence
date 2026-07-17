import csv
from pathlib import Path

from draft_room_intelligence.cli import dedupe_roster_assignments, run_report_team_depth
from draft_room_intelligence.data.team_rosters import (
    RosterPlayer,
    build_depth_rows,
    load_roster_csv,
    role_bucket,
)
from draft_room_intelligence.reports.demo_export import (
    bucket_pipeline_pressure,
    readiness_pipeline_pressure,
)

FIXTURE = Path(__file__).parent / "fixtures" / "team_rosters_sample.csv"


def test_load_roster_csv_classifies_player_roles():
    players = load_roster_csv(FIXTURE)
    by_name = {player.player_name: player for player in players}

    assert len(players) == 11
    assert role_bucket("RW") == "wing"
    assert by_name["Scoring Wing One"].role_type == "scoring_wing"
    assert by_name["Top Pair Defender"].role_type == "defense_depth"
    assert by_name["Starter Goalie"].role_type == "starter_goalie"
    assert by_name["AHL Defense Prospect"].league_level == "AHL"
    assert by_name["AHL Defense Prospect"].affiliate_of == "NYI"


def test_build_depth_rows_exposes_team_role_scarcity():
    players = load_roster_csv(FIXTURE)
    rows = [row.to_dict() for row in build_depth_rows(players)]

    nyi_two_way_defense = [
        row for row in rows if row["team_id"] == "NYI" and row["role_type"] == "two_way_defense"
    ]
    nyi_scoring_wings = [
        row for row in rows if row["team_id"] == "NYI" and row["role_type"] == "scoring_wing"
    ][0]

    assert not nyi_two_way_defense
    assert nyi_scoring_wings["players"] == "2"
    assert float(nyi_scoring_wings["scarcity_score"]) < 1.0


def test_run_report_team_depth_writes_artifacts(capsys, tmp_path):
    run_report_team_depth(FIXTURE, tmp_path)

    output = capsys.readouterr().out
    depth_csv = tmp_path / "depth.csv"
    summary_md = tmp_path / "summary.md"

    assert "# Team depth report:" in output
    assert "Roster players loaded: 11" in output
    assert depth_csv.exists()
    assert summary_md.exists()

    rows = list(csv.DictReader(depth_csv.open(newline="", encoding="utf-8")))
    assert any(row["team_id"] == "NYI" for row in rows)
    assert "Organizational Depth Report" in summary_md.read_text(encoding="utf-8")


def test_dedupe_roster_assignments_keeps_young_low_game_goalie_as_pipeline_candidate():
    players = [
        RosterPlayer(
            team_id="PIT",
            team_name="Pittsburgh Penguins",
            league_level="NHL",
            affiliate_of="",
            player_id="nhl-young-goalie",
            player_name="Young Goalie",
            position="G",
            age=22.2,
            games=5,
        ),
        RosterPlayer(
            team_id="PIT",
            team_name="Pittsburgh Penguins",
            league_level="AHL",
            affiliate_of="Wilkes-Barre/Scranton Penguins",
            player_id="ahl-young-goalie",
            player_name="Young Goalie",
            position="G",
            age=21.5,
            games=18,
        ),
        RosterPlayer(
            team_id="SJS",
            team_name="San Jose Sharks",
            league_level="NHL",
            affiliate_of="",
            player_id="nhl-starter",
            player_name="Established Starter",
            position="G",
            age=24.1,
            games=47,
        ),
        RosterPlayer(
            team_id="SJS",
            team_name="San Jose Sharks",
            league_level="AHL",
            affiliate_of="San Jose Barracuda",
            player_id="ahl-starter",
            player_name="Established Starter",
            position="G",
            age=23.2,
            games=22,
        ),
    ]

    selected = {(player.team_id, player.player_name): player for player in dedupe_roster_assignments(players)}

    assert selected[("PIT", "Young Goalie")].league_level == "AHL"
    assert selected[("SJS", "Established Starter")].league_level == "NHL"


def test_dedupe_roster_assignments_handles_accent_and_position_differences():
    players = [
        RosterPlayer("CHI", "Chicago Blackhawks", "NHL", "", "nhl-1", "Frank Nazar", "C", games=53),
        RosterPlayer("CHI", "Chicago Blackhawks", "AHL", "Rockford IceHogs", "ahl-1", "Fránk Nazar", "RW", games=21),
    ]

    selected = dedupe_roster_assignments(players)

    assert len(selected) == 1
    assert selected[0].league_level == "NHL"


def test_dedupe_roster_assignments_removes_stale_cross_organization_ahl_row():
    players = [
        RosterPlayer(
            "NJD",
            "New Jersey Devils",
            "NHL",
            "",
            "nhl-1",
            "Trade Player",
            "LW",
            age=23.4,
            games=7,
            last_game_date="2025-03-15",
        ),
        RosterPlayer(
            "TOR",
            "Toronto Maple Leafs",
            "AHL",
            "Toronto Marlies",
            "ahl-1",
            "Trade Player",
            "RW",
            age=23.6,
            games=40,
            last_game_date="2025-02-20",
        ),
    ]

    selected = dedupe_roster_assignments(players)

    assert len(selected) == 1
    assert selected[0].team_id == "NJD"
    assert selected[0].assignment_confidence == "high"


def test_dedupe_roster_assignments_uses_later_ahl_assignment_after_trade():
    players = [
        RosterPlayer(
            "TOR",
            "Toronto Maple Leafs",
            "NHL",
            "",
            "nhl-1",
            "Trade Player",
            "LW",
            age=23.4,
            games=7,
            last_game_date="2025-02-10",
        ),
        RosterPlayer(
            "PHI",
            "Philadelphia Flyers",
            "AHL",
            "Lehigh Valley Phantoms",
            "ahl-1",
            "Trade Player",
            "RW",
            age=23.6,
            games=11,
            last_game_date="2025-04-19",
        ),
    ]

    selected = dedupe_roster_assignments(players)

    assert len(selected) == 1
    assert selected[0].team_id == "PHI"


def test_dedupe_roster_assignments_marks_undated_cross_org_rows_unresolved():
    players = [
        RosterPlayer("TOR", "Toronto Maple Leafs", "NHL", "", "nhl-1", "Trade Player", "LW", age=23.4),
        RosterPlayer("PHI", "Philadelphia Flyers", "AHL", "Lehigh Valley", "ahl-1", "Trade Player", "RW", age=23.6),
    ]

    selected = dedupe_roster_assignments(players)

    assert len(selected) == 2
    assert {player.assignment_confidence for player in selected} == {"low"}
    assert {player.roster_status for player in selected} == {"cross_org_assignment_unresolved"}


def test_dedupe_roster_assignments_requires_dates_for_every_cross_org_row():
    players = [
        RosterPlayer(
            "TOR",
            "Toronto Maple Leafs",
            "NHL",
            "",
            "nhl-1",
            "Trade Player",
            "LW",
            age=23.4,
            last_game_date="2025-02-10",
        ),
        RosterPlayer("PHI", "Philadelphia Flyers", "AHL", "Lehigh Valley", "ahl-1", "Trade Player", "RW", age=23.6),
    ]

    selected = dedupe_roster_assignments(players)

    assert len(selected) == 2
    assert {player.assignment_confidence for player in selected} == {"low"}


def test_dedupe_roster_assignments_preserves_same_name_different_age():
    players = [
        RosterPlayer("NJD", "New Jersey Devils", "NHL", "", "nhl-1", "Same Name", "D", age=31.0, games=40),
        RosterPlayer("TOR", "Toronto Maple Leafs", "AHL", "Toronto Marlies", "ahl-1", "Same Name", "D", age=21.0, games=40),
    ]

    assert len(dedupe_roster_assignments(players)) == 2


def test_bucket_pipeline_pressure_penalizes_saturated_position_groups():
    assert bucket_pipeline_pressure("center", under_25=3, players=9) > 0.0
    assert bucket_pipeline_pressure("wing", under_25=6, players=24) > bucket_pipeline_pressure(
        "wing", under_25=2, players=24
    )
    assert bucket_pipeline_pressure("goalie", under_25=3, players=8) >= 0.30


def test_readiness_pipeline_pressure_weights_nhl_ready_players_more():
    assert readiness_pipeline_pressure("center", nhl_u25=2, non_nhl_u25=0) > readiness_pipeline_pressure(
        "center", nhl_u25=0, non_nhl_u25=2
    )
    assert readiness_pipeline_pressure("goalie", nhl_u25=0, non_nhl_u25=2) > 0
