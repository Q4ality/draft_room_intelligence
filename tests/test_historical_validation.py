import csv
from pathlib import Path

from draft_room_intelligence.cli import run_report_historical_validation
from draft_room_intelligence.data.normalized_tables import load_normalized_historical_prospects
from draft_room_intelligence.reports.historical_validation import build_historical_validation_report
from draft_room_intelligence.reports.historical_validation import write_historical_validation_report


PILOT = Path(__file__).parents[1] / "data" / "processed" / "pilot_2019"


def test_build_historical_validation_report_compares_baselines():
    prospects = load_normalized_historical_prospects(PILOT)

    report = build_historical_validation_report(
        prospects,
        PILOT,
        baselines=("consensus", "role-specific-hybrid"),
        precision_n=25,
        top_n=25,
    )

    assert report.prospect_count == len(prospects)
    assert report.draft_years == (2019,)
    assert [row["baseline"] for row in report.rows] == ["consensus", "role-specific-hybrid"]
    assert report.rows[0]["games_lift_delta_vs_consensus"] == ""
    assert report.rows[1]["games_lift_delta_vs_consensus"] != ""


def test_write_historical_validation_report_writes_summary_artifacts(tmp_path):
    prospects = load_normalized_historical_prospects(PILOT)

    write_historical_validation_report(
        tmp_path,
        prospects,
        PILOT,
        baselines=("consensus", "role-specific-hybrid"),
        precision_n=25,
        top_n=25,
    )

    summary_csv = tmp_path / "summary.csv"
    summary_md = tmp_path / "summary.md"
    assert summary_csv.exists()
    assert summary_md.exists()

    rows = list(csv.DictReader(summary_csv.open(newline="", encoding="utf-8")))
    assert rows[0]["baseline"] == "consensus"
    assert "Historical Validation Report" in summary_md.read_text(encoding="utf-8")


def test_run_report_historical_validation_prints_artifacts(capsys, tmp_path):
    run_report_historical_validation(PILOT, tmp_path, precision_n=25, top_n=25)

    output = capsys.readouterr().out
    assert "# Historical validation report:" in output
    assert "Prospects loaded:" in output
    assert "Summary CSV:" in output
    assert (tmp_path / "summary.csv").exists()
