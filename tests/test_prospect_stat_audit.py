import csv

from draft_room_intelligence.reports.prospect_stat_audit import write_prospect_stat_audit


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_write_prospect_stat_audit_summarizes_skaters_and_goalies(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    write_rows(
        source / "players.csv",
        [
            {"player_id": "p1", "name": "Scoring Forward", "position": "C"},
            {"player_id": "g1", "name": "Draft Goalie", "position": "G"},
        ],
    )
    write_rows(
        source / "rankings.csv",
        [
            {"player_id": "p1", "draft_year": "2025", "rank": "5", "ranking_source": "consensus"},
            {"player_id": "g1", "draft_year": "2025", "rank": "33", "ranking_source": "consensus"},
        ],
    )
    write_rows(
        source / "season_stat_lines.csv",
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "OHL",
                "team": "Example",
                "games": "20",
                "goals": "10",
                "assists": "20",
                "points": "30",
                "regular_season": "1",
                "source": "fixture",
                "source_id": "p1-ohl",
                "goalie_minutes": "",
                "shots_against": "",
                "saves": "",
                "goals_against": "",
                "save_percentage": "",
                "goals_against_average": "",
                "wins": "",
                "losses": "",
                "shutouts": "",
            },
            {
                "player_id": "g1",
                "season": "2024-25",
                "league": "USHL",
                "team": "Example",
                "games": "25",
                "goals": "",
                "assists": "",
                "points": "",
                "regular_season": "1",
                "source": "fixture",
                "source_id": "g1-ushl",
                "goalie_minutes": "1500",
                "shots_against": "800",
                "saves": "728",
                "goals_against": "72",
                "save_percentage": "",
                "goals_against_average": "",
                "wins": "15",
                "losses": "8",
                "shutouts": "3",
            },
        ],
    )

    output = tmp_path / "audit"
    summary = write_prospect_stat_audit(output, [source], draft_year=2025)

    assert summary == {"players": 2, "stat_lines": 2, "goalies": 1, "flags": 2}
    prospect_rows = list(csv.DictReader((output / "prospect_stat_summary.csv").open()))
    by_name = {row["name"]: row for row in prospect_rows}
    assert by_name["Scoring Forward"]["points_per_game"] == "1.500"
    assert by_name["Draft Goalie"]["goalie_save_percentage"] == "0.910"
    assert by_name["Draft Goalie"]["goalie_goals_against_average"] == "2.88"
    assert by_name["Draft Goalie"]["goalie_quality_score"]
    assert (output / "summary.md").exists()
