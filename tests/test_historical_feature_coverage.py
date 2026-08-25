import csv

from draft_room_intelligence.reports.historical_feature_coverage import (
    build_historical_feature_coverage_report,
    write_historical_feature_coverage_report,
)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_feature_coverage_excludes_draft_slot_proxy_from_consensus(tmp_path):
    final = tmp_path / "classes" / "2018" / "final"
    write_csv(final / "players.csv", ["player_id"], [{"player_id": "p1"}, {"player_id": "p2"}])
    write_csv(
        final / "rankings.csv",
        ["player_id", "rank", "source"],
        [
            {"player_id": "p1", "rank": "1", "source": "draft_slot_proxy"},
            {"player_id": "p2", "rank": "2", "source": "independent_consensus"},
        ],
    )
    write_csv(
        final / "season_stat_lines.csv",
        ["player_id"],
        [{"player_id": "p1"}, {"player_id": "p2"}],
    )
    write_csv(final / "advanced_stat_lines.csv", ["player_id"], [])

    report = build_historical_feature_coverage_report(
        tmp_path / "classes", start_year=2018, end_year=2018
    )

    row = report.rows[0]
    assert row["consensus_player_count"] == "1"
    assert row["draft_slot_proxy_player_count"] == "1"
    assert row["production_player_count"] == "2"
    assert row["status"] == "needs_consensus"

    write_historical_feature_coverage_report(
        tmp_path / "classes", tmp_path / "report", start_year=2018, end_year=2018
    )
    assert (tmp_path / "report" / "coverage.csv").exists()
    assert "draft_slot_proxy" in (tmp_path / "report" / "summary.md").read_text(encoding="utf-8")
