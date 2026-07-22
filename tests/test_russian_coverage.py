import csv

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.reports.russian_coverage import write_russian_coverage_report


def test_russian_coverage_report_builds_missing_player_queue(tmp_path):
    dataset = tmp_path / "final"
    output = tmp_path / "report"
    dataset.mkdir()
    write_table(
        dataset / "players.csv",
        PLAYER_COLUMNS,
        [
            {"player_id": "covered", "name": "Covered Player", "nationality": "RUS"},
            {"player_id": "missing", "name": "Missing Player", "nationality": "RUS"},
            {"player_id": "junior", "name": "Junior Player", "nationality": "RUS"},
            {"player_id": "second-tier", "name": "Second Tier Player", "nationality": "RUS"},
            {"player_id": "external", "name": "External Player", "nationality": "RUS"},
        ],
    )
    write_table(
        dataset / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "covered",
                "season": "2025-26",
                "league": "MHL",
                "team": "Test Club",
                "games": "40",
                "timing": "pre_draft",
                "regular_season": "true",
                "source_url": "https://example.test/regular",
            },
            {
                "player_id": "covered",
                "season": "2025-26",
                "league": "MHL",
                "team": "Test Club",
                "games": "12",
                "timing": "pre_draft",
                "regular_season": "false",
                "source_url": "https://example.test/playoffs",
            },
        ],
    )
    with (dataset / "draft_selections.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["player_id", "drafted_from_league"])
        writer.writeheader()
        writer.writerows(
            [
                {"player_id": "covered", "drafted_from_league": "RUSSIA"},
                {"player_id": "missing", "drafted_from_league": "RUSSIA"},
                {"player_id": "junior", "drafted_from_league": "Russia Jr."},
                {"player_id": "second-tier", "drafted_from_league": "RUSSIA-2"},
                {"player_id": "external", "drafted_from_league": "OHL"},
            ]
        )

    report = write_russian_coverage_report(dataset, output, draft_year=2026)

    assert report.russian_players == 5
    assert report.russian_league_targets == 4
    assert report.covered_players == 1
    assert report.external_league_players == 1
    assert report.missing_players == 3
    assert report.playoff_players == 1
    with (output / "review_queue.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["name"] == "Junior Player"
    assert rows[1]["name"] == "Missing Player"
    assert rows[2]["name"] == "Second Tier Player"
    assert rows[3]["coverage_status"] == "external_league"
    assert rows[4]["regular_games"] == "40"
    assert rows[4]["playoff_games"] == "12"
