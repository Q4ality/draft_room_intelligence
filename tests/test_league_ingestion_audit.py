import csv

from draft_room_intelligence.reports.league_ingestion_audit import (
    build_league_ingestion_audit,
    write_league_ingestion_audit,
)


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_audit_reports_conflicts_partial_advanced_and_unmatched_rows(tmp_path):
    final = tmp_path / "classes" / "2025" / "final"
    final.mkdir(parents=True)
    write_csv(
        final / "players.csv",
        ["player_id", "name"],
        [{"player_id": "p1", "name": "Example Defender"}, {"player_id": "p2", "name": "Missing"}],
    )
    fields = [
        "player_id",
        "season",
        "league",
        "games",
        "goals",
        "assists",
        "points",
        "timing",
        "regular_season",
        "source",
    ]
    write_csv(
        final / "season_stat_lines.csv",
        fields,
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "SHL",
                "games": "40",
                "goals": "3",
                "assists": "8",
                "points": "11",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "one",
            },
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "SHL",
                "games": "41",
                "goals": "3",
                "assists": "9",
                "points": "12",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "two",
            },
        ],
    )
    write_csv(
        final / "advanced_stat_lines.csv",
        [
            "player_id",
            "season",
            "league",
            "games",
            "timing",
            "regular_season",
            "plus_minus",
            "source",
        ],
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "SHL",
                "games": "20",
                "timing": "pre_draft",
                "regular_season": "true",
                "plus_minus": "5",
                "source": "one",
            }
        ],
    )
    write_csv(
        final / "europe_stat_matches.csv",
        ["player_id", "name", "matched"],
        [{"player_id": "p1", "name": "Example Defender", "matched": "false"}],
    )

    report = build_league_ingestion_audit(tmp_path / "classes", start_year=2025, end_year=2025)

    assert report.years[0].players_with_pre_draft_stats == 1
    assert report.years[0].conflicting_stat_keys == 1
    assert report.years[0].partial_advanced_rows == 1
    assert report.years[0].unmatched_audit_rows == 1
    assert {row["issue_type"] for row in report.issues} == {
        "conflicting_stat_key",
        "partial_advanced_sample",
        "unmatched_source_audit",
    }


def test_write_audit_keeps_missing_years_visible(tmp_path):
    report = write_league_ingestion_audit(
        tmp_path / "classes",
        tmp_path / "report",
        start_year=2024,
        end_year=2025,
    )

    assert len(report.years) == 2
    assert (tmp_path / "report" / "year_summary.csv").is_file()
    assert "| 2024 | 0/0" in (tmp_path / "report" / "summary.md").read_text(encoding="utf-8")
