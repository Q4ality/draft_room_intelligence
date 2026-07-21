import csv
import json

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.ushl_stats import (
    UShlStatSource,
    enrich_ushl_stats,
    parse_ushl_goalies_json,
    parse_ushl_skaters_json,
)


def ushl_payload(*rows):
    return json.dumps([{"sections": [{"title": "Skaters", "headers": {}, "data": list(rows)}]}])


ROW = {
    "prop": {},
    "row": {
        "name": "Vaclav Nestrasil",
        "player_id": "11589",
        "team_code": "MUS",
        "games_played": "61",
        "goals": "19",
        "assists": "23",
        "points": "42",
    },
}


def test_parse_ushl_skaters_json_extracts_core_stats():
    rows = parse_ushl_skaters_json(
        ushl_payload(ROW),
        UShlStatSource(season="2024-25", season_id="85", regular_season=True),
    )

    assert len(rows) == 1
    assert rows[0].name == "Vaclav Nestrasil"
    assert rows[0].source_id == "11589"
    assert rows[0].team == "MUS"
    assert rows[0].games == "61"
    assert rows[0].goals == "19"
    assert rows[0].assists == "23"
    assert rows[0].points == "42"
    assert rows[0].regular_season is True


def test_parse_ushl_goalies_json_extracts_role_specific_stats():
    row = {
        "row": {
            "name": "Sample Goalie",
            "player_id": "9001",
            "team_code": "USA",
            "games_played": "20",
            "minutes_played": 1100,
            "shots": "600",
            "goals_against": "48",
            "save_percentage": "0.920",
            "goals_against_average": "2.62",
            "wins": "12",
            "losses": "5",
            "ot_losses": "2",
            "shutouts": "3",
        }
    }

    rows = parse_ushl_goalies_json(
        ushl_payload(row),
        UShlStatSource(
            season="2024-25",
            season_id="85",
            regular_season=True,
            position="goalies",
        ),
    )

    assert rows[0].games == "20"
    assert rows[0].shots_against == "600"
    assert rows[0].saves == "552"
    assert rows[0].save_percentage == "0.920"
    assert rows[0].goals_against_average == "2.62"
    assert rows[0].ties == "2"
    assert rows[0].shutouts == "3"


def test_enrich_ushl_stats_replaces_matching_placeholder_rows(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "ushl.json"
    base_dir.mkdir()
    source_path.write_text(ushl_payload(ROW), encoding="utf-8")
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-025-vaclav-nestrasil",
                "name": "Vaclav Nestrasil",
                "birth_date": "",
                "nationality": "Czechia",
                "position": "RW",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-025-vaclav-nestrasil",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-025-vaclav-nestrasil",
                "season": "2024-25",
                "league": "USHL",
                "team": "Muskegon Lumberjacks",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-025-vaclav-nestrasil",
                "source_url": "",
            }
        ],
    )

    summary = enrich_ushl_stats(
        base_dir,
        output_dir,
        [
            UShlStatSource(
                season="2024-25",
                season_id="85",
                regular_season=True,
                source_path=source_path,
            )
        ],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))
    with (output_dir / "ushl_stat_matches.csv").open(newline="", encoding="utf-8") as file:
        matches = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 1
    assert stat_lines[0]["source"] == "ushl"
    assert stat_lines[0]["games"] == "61"
    assert stat_lines[0]["points"] == "42"
    assert matches[0]["matched"] == "true"
