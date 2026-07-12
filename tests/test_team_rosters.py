import csv
from pathlib import Path

from draft_room_intelligence.cli import run_report_team_depth
from draft_room_intelligence.data.team_rosters import build_depth_rows
from draft_room_intelligence.data.team_rosters import load_roster_csv
from draft_room_intelligence.data.team_rosters import role_bucket


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
