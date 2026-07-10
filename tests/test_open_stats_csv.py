import csv

from draft_room_intelligence.data.eliteprospects_csv import PLAYER_COLUMNS, SEASON_STAT_LINE_COLUMNS, write_table
from draft_room_intelligence.data.open_stats_csv import OpenStatsCsvSource, enrich_open_stats_csv


def test_enrich_open_stats_csv_replaces_placeholder_and_keeps_goalie_metrics(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "ncaa.csv"
    base_dir.mkdir()
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "name": "James Hagens",
                "birth_date": "",
                "nationality": "United States",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-007-james-hagens",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "season": "2024-25",
                "league": "NCAA",
                "team": "Boston College",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-007-james-hagens",
                "source_url": "",
            }
        ],
    )
    source_path.write_text(
        "\n".join(
            [
                "name,league,team,games,goals,assists,points,source_url",
                "James Hagens,NCAA,Boston College,37,11,26,37,https://example.test/james-hagens",
            ]
        ),
        encoding="utf-8",
    )

    summary = enrich_open_stats_csv(
        base_dir,
        output_dir,
        [OpenStatsCsvSource(path=source_path, source="collegehockeyinc", season="2024-25", league="NCAA")],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 1
    assert stat_lines[0]["source"] == "open-stats"
    assert stat_lines[0]["games"] == "37"
    assert stat_lines[0]["points"] == "37"
    assert stat_lines[0]["source_url"] == "https://example.test/james-hagens"
