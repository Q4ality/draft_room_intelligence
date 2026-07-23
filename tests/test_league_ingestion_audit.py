import csv

from draft_room_intelligence.reports.league_ingestion_audit import (
    build_league_ingestion_audit,
    conflicting_key_issues,
    unmatched_audit_issues,
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
            {
                "player_id": "p2",
                "season": "2024-25",
                "league": "OHL",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "placeholder",
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
    write_csv(
        final / "draft_selections.csv",
        ["player_id", "overall_pick", "drafted_from_team", "drafted_from_league"],
        [
            {
                "player_id": "p1",
                "overall_pick": "4",
                "drafted_from_team": "Example Club",
                "drafted_from_league": "SHL",
            },
            {
                "player_id": "p2",
                "overall_pick": "42",
                "drafted_from_team": "Missing Club",
                "drafted_from_league": "OHL",
            },
        ],
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
    assert len(report.coverage_gaps) == 1
    assert report.coverage_gaps[0]["player_name"] == "Missing"
    assert report.coverage_gaps[0]["priority"] == "high"
    assert report.coverage_gaps[0]["source_family"] == "CHL"


def test_write_audit_keeps_missing_years_visible(tmp_path):
    report = write_league_ingestion_audit(
        tmp_path / "classes",
        tmp_path / "report",
        start_year=2024,
        end_year=2025,
    )

    assert len(report.years) == 2
    assert (tmp_path / "report" / "year_summary.csv").is_file()
    assert (tmp_path / "report" / "coverage_gaps.csv").is_file()
    assert "| 2024 | 0/0" in (tmp_path / "report" / "summary.md").read_text(encoding="utf-8")


def test_audit_detects_same_scope_skater_goalie_collision():
    common = {
        "player_id": "g1",
        "season": "2024-25",
        "league": "USHL",
        "team": "NTDP",
        "regular_season": "true",
        "games": "20",
        "source": "ushl",
    }
    issues = conflicting_key_issues(
        2025,
        [
            {**common, "goals": "0", "assists": "1", "points": "1"},
            {**common, "save_percentage": "0.920", "wins": "12"},
        ],
        {"g1": "Goalie Example"},
    )

    assert {row["issue_type"] for row in issues} == {"conflicting_role_stat_key"}


def test_unmatched_audit_uses_explicit_eligible_disposition_without_stat_row(tmp_path):
    final = tmp_path / "final"
    final.mkdir()
    write_csv(
        final / "ushl_stat_matches.csv",
        ["player_id", "name", "matched", "disposition"],
        [
            {
                "player_id": "p1",
                "name": "Missing Eligible Player",
                "matched": "false",
                "disposition": "unmatched_in_cached_source",
            },
            {
                "player_id": "p2",
                "name": "Ineligible Player",
                "matched": "false",
                "disposition": "not_eligible",
            },
        ],
    )

    issues = unmatched_audit_issues(
        2025,
        final,
        {"p1": "Missing Eligible Player", "p2": "Ineligible Player"},
        {},
    )

    assert [row["player_id"] for row in issues] == ["p1"]
    assert issues[0]["detail"] == "unmatched_in_cached_source"


def test_audit_reports_goalie_and_advanced_conflicts(tmp_path):
    final = tmp_path / "classes" / "2025" / "final"
    final.mkdir(parents=True)
    write_csv(
        final / "players.csv",
        ["player_id", "name"],
        [{"player_id": "g1", "name": "Goalie Example"}],
    )
    common = {
        "player_id": "g1",
        "season": "2024-25",
        "league": "Liiga",
        "team": "Example",
        "timing": "pre_draft",
        "regular_season": "true",
    }
    write_csv(
        final / "season_stat_lines.csv",
        [*common, "games", "wins", "losses", "source"],
        [
            {**common, "games": "10", "wins": "6", "losses": "4", "source": "one"},
            {**common, "games": "11", "wins": "7", "losses": "4", "source": "two"},
        ],
    )
    write_csv(
        final / "advanced_stat_lines.csv",
        [*common, "games", "shots", "source"],
        [
            {**common, "games": "10", "shots": "20", "source": "one"},
            {**common, "games": "11", "shots": "24", "source": "two"},
        ],
    )

    report = build_league_ingestion_audit(
        tmp_path / "classes",
        start_year=2025,
        end_year=2025,
    )

    issue_types = {row["issue_type"] for row in report.issues}
    assert "conflicting_goalie_stat_key" in issue_types
    assert "conflicting_advanced_stat_key" in issue_types
    assert report.years[0].conflicting_stat_keys == 2


def test_audit_skips_provider_not_configured_match_rows(tmp_path):
    final = tmp_path / "classes" / "2025" / "final"
    final.mkdir(parents=True)
    write_csv(
        final / "players.csv",
        ["player_id", "name"],
        [{"player_id": "p1", "name": "Russian Prospect"}],
    )
    write_csv(
        final / "season_stat_lines.csv",
        ["player_id", "season", "league", "timing", "regular_season"],
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "MHL",
                "timing": "pre_draft",
                "regular_season": "true",
            }
        ],
    )
    write_csv(
        final / "europe_stat_matches.csv",
        ["player_id", "name", "matched", "match_method"],
        [
            {
                "player_id": "p1",
                "name": "Russian Prospect",
                "matched": "false",
                "match_method": "not_configured",
            }
        ],
    )

    report = build_league_ingestion_audit(
        tmp_path / "classes",
        start_year=2025,
        end_year=2025,
    )

    assert report.years[0].unmatched_audit_rows == 0
