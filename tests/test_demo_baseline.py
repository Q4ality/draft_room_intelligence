import json
from pathlib import Path

from draft_room_intelligence.data.historical_csv import load_historical_prospects_csv
from draft_room_intelligence.reports.demo_baseline import build_demo_baseline
from draft_room_intelligence.reports.demo_export import build_demo_export_bundle

FIXTURE = Path(__file__).parent / "fixtures" / "historical_prospects.csv"


def test_demo_baseline_fingerprint_is_stable_and_content_sensitive(tmp_path):
    prospects = load_historical_prospects_csv(FIXTURE)
    bundle = build_demo_export_bundle(prospects)

    first = build_demo_baseline(
        FIXTURE,
        prospects,
        bundle.board_rows,
        bundle.player_details,
    )
    second = build_demo_baseline(
        FIXTURE,
        prospects,
        bundle.board_rows,
        bundle.player_details,
    )

    assert first == second
    assert first["metrics"]["player_count"] == 2
    assert first["metrics"]["season_stat_line_count"] >= 2

    changed = tmp_path / "historical_prospects.csv"
    changed.write_text(FIXTURE.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed_baseline = build_demo_baseline(
        changed,
        prospects,
        bundle.board_rows,
        bundle.player_details,
    )

    assert changed_baseline["baseline_id"] != first["baseline_id"]
    json.dumps(first)


def test_demo_baseline_ignores_duplicate_supporting_input(tmp_path):
    prospects = load_historical_prospects_csv(FIXTURE)
    bundle = build_demo_export_bundle(prospects)
    support = tmp_path / "depth.csv"
    support.write_text("team_id,player_id\nNYI,p1\n", encoding="utf-8")

    direct = build_demo_baseline(
        FIXTURE,
        prospects,
        bundle.board_rows,
        bundle.player_details,
        supporting_paths=[support],
    )
    with_duplicate = build_demo_baseline(
        FIXTURE,
        prospects,
        bundle.board_rows,
        bundle.player_details,
        supporting_paths=[FIXTURE, support],
    )

    assert with_duplicate["baseline_id"] == direct["baseline_id"]
    assert with_duplicate["source_files"] == direct["source_files"]
