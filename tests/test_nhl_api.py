from datetime import date
from pathlib import Path

import pytest

from draft_room_intelligence.data.nhl_api import (
    import_nhl_rosters,
    load_roster_payload,
    parse_nhl_roster_payload,
    read_json_payload,
    resolve_season_assignments,
)
from draft_room_intelligence.data.team_rosters import RosterPlayer, load_roster_csv

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
    assert by_name["Mathew Barzal"].snapshot_date == "2026-07-01"
    assert by_name["Mathew Barzal"].snapshot_type == "current_roster"
    assert by_name["Mathew Barzal"].assignment_confidence == "high"


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


def test_load_roster_payload_prefers_season_specific_cache(tmp_path):
    (tmp_path / "NYI.roster.json").write_text('{"name": "current"}', encoding="utf-8")
    (tmp_path / "NYI.20242025.roster.json").write_text('{"name": "historical"}', encoding="utf-8")

    payload = load_roster_payload(
        "NYI",
        season="20242025",
        roster_json_dir=tmp_path,
    )

    assert payload["name"] == "historical"


def test_load_historical_roster_does_not_fall_back_to_generic_current_cache(tmp_path):
    (tmp_path / "NYI.roster.json").write_text('{"name": "current"}', encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        load_roster_payload("NYI", season="20242025", roster_json_dir=tmp_path)


def test_import_historical_roster_marks_season_provenance(tmp_path):
    output_csv = tmp_path / "nhl_rosters.csv"
    (tmp_path / "NYI.20242025.roster.json").write_text(
        (FIXTURE_DIR / "NYI.roster.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "NYI.20242025.2.stats.json").write_text(
        (FIXTURE_DIR / "NYI.stats.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    import_nhl_rosters(
        output_csv,
        team_codes=["NYI"],
        season="20242025",
        roster_json_dir=tmp_path,
        stats_json_dir=tmp_path,
    )

    players = load_roster_csv(output_csv)
    assert {player.snapshot_date for player in players} == {"2025-06-01"}
    assert {player.snapshot_type for player in players} == {"season_participation"}
    assert {player.assignment_confidence for player in players} == {"medium"}
    assert {player.source for player in players} == {"nhl_api_club_stats"}


def test_import_historical_roster_requires_season_specific_stats(tmp_path):
    output_csv = tmp_path / "nhl_rosters.csv"
    (tmp_path / "NYI.20242025.roster.json").write_text(
        (FIXTURE_DIR / "NYI.roster.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="requires club stats"):
        import_nhl_rosters(
            output_csv,
            team_codes=["NYI"],
            season="20242025",
            roster_json_dir=tmp_path,
            stats_json_dir=tmp_path,
        )


def test_resolve_season_assignments_uses_last_game_team(tmp_path):
    player_dir = tmp_path / "players"
    player_dir.mkdir()
    (player_dir / "1.20242025.2.game-log.json").write_text(
        '{"gameLog": [{"gameId": 2, "gameDate": "2025-04-01", "teamAbbrev": "EDM"}, '
        '{"gameId": 1, "gameDate": "2025-02-01", "teamAbbrev": "BOS"}]}',
        encoding="utf-8",
    )
    players = [
        RosterPlayer("BOS", "Boston Bruins", "NHL", "", "nhl-1", "Trade Player", "C", games=57, source_id="1"),
        RosterPlayer("EDM", "Edmonton Oilers", "NHL", "", "nhl-1", "Trade Player", "C", games=1, source_id="1"),
    ]

    resolved = resolve_season_assignments(
        players,
        season="20242025",
        game_type=2,
        cache_json_dir=tmp_path,
        allow_fetch=False,
    )

    assert len(resolved) == 1
    assert resolved[0].team_id == "EDM"


def test_resolve_season_assignments_marks_fallback_low_confidence(tmp_path):
    players = [
        RosterPlayer("BOS", "Boston Bruins", "NHL", "", "nhl-2", "Unknown Trade", "C", games=50, source_id="2"),
        RosterPlayer("EDM", "Edmonton Oilers", "NHL", "", "nhl-2", "Unknown Trade", "C", games=2, source_id="2"),
    ]

    resolved = resolve_season_assignments(
        players,
        season="20242025",
        game_type=2,
        cache_json_dir=tmp_path,
        allow_fetch=False,
    )

    assert resolved[0].team_id == "BOS"
    assert resolved[0].assignment_confidence == "low"
    assert resolved[0].roster_status == "season_participant_unresolved_assignment"
