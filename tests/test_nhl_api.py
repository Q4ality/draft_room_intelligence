from datetime import date
from pathlib import Path

from draft_room_intelligence.data.nhl_api import import_nhl_rosters
from draft_room_intelligence.data.nhl_api import parse_nhl_roster_payload
from draft_room_intelligence.data.nhl_api import read_json_payload
from draft_room_intelligence.data.team_rosters import load_roster_csv


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "nhl_api"


def test_parse_nhl_roster_payload_maps_bio_stats_and_roles():
    roster_payload = read_json_payload(FIXTURE_DIR / "NYI.roster.json")
    stats_payload = read_json_payload(FIXTURE_DIR / "NYI.stats.json")

    players = parse_nhl_roster_payload(
        "NYI",
        roster_payload,
        stats_payload=stats_payload,
        as_of=date(2026, 7, 1),
    )
    by_name = {player.player_name: player for player in players}

    assert len(players) == 4
    assert by_name["Mathew Barzal"].team_name == "New York Islanders"
    assert by_name["Mathew Barzal"].player_id == "nhl-8478445"
    assert by_name["Mathew Barzal"].age == 29.1
    assert by_name["Mathew Barzal"].height_cm == 183
    assert by_name["Mathew Barzal"].weight_kg == 85
    assert by_name["Mathew Barzal"].games == 82
    assert by_name["Mathew Barzal"].points == 80
    assert by_name["Mathew Barzal"].time_on_ice_per_game == 20.5
    assert by_name["Mathew Barzal"].role_type == "scoring_center"
    assert by_name["Scoring Wing"].role_type == "scoring_wing"
    assert by_name["Scoring Wing"].time_on_ice_per_game == 17.2
    assert by_name["Depth Defender"].role_type == "defense_depth"
    assert by_name["Starter Goalie"].role_type == "starter_goalie"
    assert by_name["Starter Goalie"].goalie_wins == 31
    assert by_name["Starter Goalie"].goalie_saves == 1420
    assert by_name["Starter Goalie"].goalie_shots_against == 1560
    assert by_name["Starter Goalie"].goalie_goals_against == 140
    assert by_name["Starter Goalie"].goalie_save_percentage == 0.910
    assert by_name["Starter Goalie"].goalie_goals_against_average == 2.69
    assert by_name["Starter Goalie"].goalie_shutouts == 4


def test_import_nhl_rosters_writes_normalized_csv(tmp_path):
    output_csv = tmp_path / "nhl_rosters.csv"

    summary = import_nhl_rosters(
        output_csv,
        team_codes=["nyi"],
        roster_json_dir=FIXTURE_DIR,
        stats_json_dir=FIXTURE_DIR,
        as_of=date(2026, 7, 1),
    )
    players = load_roster_csv(output_csv)

    assert summary.teams_requested == 1
    assert summary.teams_loaded == 1
    assert summary.roster_players == 4
    assert summary.stats_teams_loaded == 1
    assert len(players) == 4
    assert {player.league_level for player in players} == {"NHL"}
    assert {player.source for player in players} == {"nhl_api"}
