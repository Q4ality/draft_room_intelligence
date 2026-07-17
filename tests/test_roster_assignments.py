import json

from draft_room_intelligence.data.roster_assignments import latest_ahl_game_date, latest_nhl_game_date
from draft_room_intelligence.data.team_rosters import RosterPlayer


def test_latest_ahl_game_date_filters_games_to_assignment_team(tmp_path):
    cache_path = tmp_path / "ahl" / "10428.86.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            {
                "gameByGame": [
                    {
                        "sections": [
                            {
                                "data": [
                                    {"row": {"game": "TOR @ BEL", "date_played": "2025-02-28"}},
                                    {"row": {"game": "LV @ HER", "date_played": "2025-04-19"}},
                                ]
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    player = RosterPlayer(
        "PHI", "Philadelphia Flyers", "AHL", "Lehigh Valley", "ahl-10428", "Nikita Grebenkin", "LW", source_id="86:LV:10428"
    )

    assert latest_ahl_game_date(player, cache_json_dir=tmp_path) == "2025-04-19"


def test_latest_nhl_game_date_uses_cached_official_log(tmp_path):
    cache_path = tmp_path / "nhl" / "8483733.20242025.2.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps({"gameLog": [{"gameDate": "2024-12-20"}, {"gameDate": "2025-02-01"}]}),
        encoding="utf-8",
    )
    player = RosterPlayer(
        "TOR", "Toronto Maple Leafs", "NHL", "", "nhl-8483733", "Nikita Grebenkin", "LW", source_id="8483733"
    )

    assert latest_nhl_game_date(
        player,
        season="20242025",
        game_type=2,
        cache_json_dir=tmp_path,
    ) == "2025-02-01"
