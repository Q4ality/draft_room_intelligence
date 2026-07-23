from pathlib import Path

import pytest

from draft_room_intelligence.data.demo_snapshot import create_demo_snapshot, load_demo_snapshot


def write_final_dataset(path: Path) -> None:
    path.mkdir(parents=True)
    for name in ("players.csv", "draft_selections.csv", "rankings.csv", "season_stat_lines.csv"):
        (path / name).write_text("column\nvalue\n", encoding="utf-8")
    (path / "advanced_stat_lines.csv").write_text("column\nvalue\n", encoding="utf-8")


def test_demo_snapshot_is_self_contained_and_verifiable(tmp_path):
    source = tmp_path / "source"
    write_final_dataset(source)
    depth = tmp_path / "depth.csv"
    depth.write_text("team_id\nNYI\n", encoding="utf-8")

    created = create_demo_snapshot(
        source,
        tmp_path / "snapshot",
        draft_year=2025,
        team_depth_csv=depth,
    )
    loaded = load_demo_snapshot(created.root)

    assert loaded.draft_year == 2025
    assert loaded.snapshot_id == created.snapshot_id
    assert loaded.team_depth_csv == created.root / "team_depth.csv"
    assert loaded.advanced_stats_csv == created.root / "final" / "advanced_stat_lines.csv"


def test_demo_snapshot_rejects_changed_inputs(tmp_path):
    source = tmp_path / "source"
    write_final_dataset(source)
    created = create_demo_snapshot(source, tmp_path / "snapshot", draft_year=2025)
    (created.data_dir / "players.csv").write_text("column\nchanged\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksums"):
        load_demo_snapshot(created.root)
