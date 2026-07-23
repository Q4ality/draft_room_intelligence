import json
from pathlib import Path

from draft_room_intelligence.cli import run_build_demo_readiness


FIXTURE = Path(__file__).parent / "fixtures" / "historical_prospects.csv"


def test_run_build_demo_readiness_writes_site_and_reports(capsys, tmp_path):
    run_build_demo_readiness(FIXTURE, tmp_path, gap_top_n=2, movement_top_n=2)

    output = capsys.readouterr().out

    assert "# Demo readiness build:" in output
    assert "Dataset status:" in output
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "board.csv").exists()
    assert (tmp_path / "players.json").exists()
    assert (tmp_path / "baseline.json").exists()
    assert (tmp_path / "reports" / "data_gaps" / "summary.md").exists()
    assert (tmp_path / "reports" / "data_gaps" / "priority_gaps.csv").exists()
    assert (tmp_path / "reports" / "modeling_sanity" / "summary.md").exists()
    assert (tmp_path / "reports" / "modeling_sanity" / "largest_movements.csv").exists()
    baseline = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["baseline_id"] == baseline["baseline_id"]
    assert manifest["baseline_metrics"] == baseline["metrics"]
    assert baseline["metrics"]["player_count"] == 2
