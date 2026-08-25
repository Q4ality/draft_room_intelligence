import csv
from datetime import date

from draft_room_intelligence.cli import run_report_outcome_label_coverage
from draft_room_intelligence.data.draft_range_etl import load_draft_class_manifest
from draft_room_intelligence.reports.outcome_label_coverage import (
    build_outcome_label_coverage_report,
    write_outcome_label_coverage_report,
)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(path):
    write_csv(
        path,
        [
            "draft_year",
            "enabled",
            "base_dir",
            "nhl_draft_json",
            "hockeydb_draft_html",
            "hockeydb_player_pages_dir",
            "eliteprospects_csv",
            "match_map",
            "output_dir",
            "notes",
        ],
        [
            {"draft_year": "2018", "enabled": "true", "base_dir": "class_2018"},
            {"draft_year": "2021", "enabled": "true", "base_dir": "class_2021"},
        ],
    )


def canonical_row(player_id, draft_year, horizon_years, outcome_through):
    return {
        "player_id": player_id,
        "draft_year": str(draft_year),
        "horizon_years": str(horizon_years),
        "outcome_through": outcome_through,
        "nhl_games": "100",
        "nhl_points": "30",
        "nhl_toi_minutes": "1000",
        "goalie_starts": "0",
        "value_proxy": "1.0",
        "source": "example",
        "source_id": player_id,
        "source_url": "https://example.test/outcomes",
    }


def test_coverage_requires_time_bounded_fields_and_respects_maturity(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    write_manifest(manifest_path)
    write_csv(
        tmp_path / "class_2018" / "players.csv",
        ["player_id"],
        [{"player_id": "p-2018"}],
    )
    write_csv(
        tmp_path / "class_2018" / "nhl_outcomes.csv",
        ["player_id", "nhl_games", "nhl_points", "source", "source_id", "source_url"],
        [
            {
                "player_id": "p-2018",
                "nhl_games": "100",
                "nhl_points": "30",
                "source": "example",
                "source_id": "p-2018",
                "source_url": "https://example.test/p-2018",
            }
        ],
    )
    specs = load_draft_class_manifest(manifest_path, project_root=tmp_path)

    report = build_outcome_label_coverage_report(specs, as_of_date=date(2026, 8, 16))

    statuses = {(row["draft_year"], row["horizon_years"]): row["status"] for row in report.rows}
    assert statuses[("2018", "3")] == "requires_time_bounded_export"
    assert statuses[("2021", "7")] == "not_mature_yet"
    assert statuses[("2021", "3")] == "missing_normalized_class"


def test_coverage_requires_complete_mature_canonical_labels(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    write_manifest(manifest_path)
    write_csv(
        tmp_path / "class_2018" / "players.csv",
        ["player_id"],
        [{"player_id": "p-2018"}],
    )
    fields = list(canonical_row("p-2018", 2018, 3, "2021-06-30"))
    write_csv(
        tmp_path / "class_2018" / "nhl_outcomes.csv",
        fields,
        [canonical_row("p-2018", 2018, 3, "2021-06-30")],
    )
    specs = load_draft_class_manifest(manifest_path, project_root=tmp_path)

    report = build_outcome_label_coverage_report(specs, as_of_date=date(2026, 8, 16))
    statuses = {(row["draft_year"], row["horizon_years"]): row["status"] for row in report.rows}
    assert statuses[("2018", "3")] == "ready_for_label_audit"
    assert statuses[("2018", "5")] == "incomplete_canonical_labels"

    write_csv(
        tmp_path / "class_2018" / "nhl_outcomes.csv",
        fields,
        [canonical_row("p-unknown", 2018, 3, "2021-06-30")],
    )
    report = build_outcome_label_coverage_report(specs, as_of_date=date(2026, 8, 16))
    assert report.rows[0]["status"] == "incomplete_canonical_labels"

    write_csv(
        tmp_path / "class_2018" / "nhl_outcomes.csv",
        fields,
        [canonical_row("p-2018", 2018, 3, "2020-06-30")],
    )
    report = build_outcome_label_coverage_report(specs, as_of_date=date(2026, 8, 16))
    assert report.rows[0]["status"] == "immature_canonical_labels"


def test_coverage_writer_and_cli_create_report_artifacts(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.csv"
    write_manifest(manifest_path)
    specs = load_draft_class_manifest(manifest_path, project_root=tmp_path)

    report = write_outcome_label_coverage_report(
        specs, tmp_path / "report", as_of_date=date(2026, 8, 16)
    )
    assert len(report.rows) == 6
    assert (tmp_path / "report" / "coverage.csv").exists()
    assert "missing_normalized_class" in (
        tmp_path / "report" / "summary.md"
    ).read_text(encoding="utf-8")

    run_report_outcome_label_coverage(
        manifest_path,
        tmp_path / "cli-report",
        project_root=tmp_path,
        as_of_date=date(2026, 8, 16),
        start_year=2014,
        end_year=2021,
    )
    assert "# Longitudinal outcome label coverage:" in capsys.readouterr().out
