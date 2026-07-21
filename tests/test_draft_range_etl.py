import csv
from dataclasses import replace
from pathlib import Path

import pytest

from draft_room_intelligence.data.draft_range_etl import (
    DraftClassETLSpec,
    audit_normalized_dataset,
    filter_draft_class_specs,
    load_draft_class_manifest,
    plan_draft_class,
    run_draft_range_etl,
)


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
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
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_normalized_dataset(path: Path, draft_year: int = 2019) -> None:
    path.mkdir(parents=True, exist_ok=True)
    player_rows = "\n".join(
        f"p{pick},Player {pick},C,fixture" for pick in range(1, 151)
    )
    selection_rows = "\n".join(
        f"p{pick},{draft_year},TST,1,{pick},fixture" for pick in range(1, 151)
    )
    ranking_rows = "\n".join(
        f"p{pick},{draft_year},fixture,{pick}" for pick in range(1, 151)
    )
    (path / "players.csv").write_text(
        f"player_id,name,position,source\n{player_rows}\n",
        encoding="utf-8",
    )
    (path / "draft_selections.csv").write_text(
        "player_id,draft_year,team_id,round_number,overall_pick,source\n"
        f"{selection_rows}\n",
        encoding="utf-8",
    )
    (path / "rankings.csv").write_text(
        f"player_id,draft_year,source,rank\n{ranking_rows}\n",
        encoding="utf-8",
    )
    (path / "season_stat_lines.csv").write_text(
        "player_id,season,league,team,timing\np1,2018-19,OHL,Example,pre_draft\n",
        encoding="utf-8",
    )
    (path / "nhl_outcomes.csv").write_text(
        "player_id,nhl_games,nhl_points\n",
        encoding="utf-8",
    )


def spec(tmp_path: Path, year: int, *, base: bool = True) -> DraftClassETLSpec:
    base_dir = tmp_path / "base" / str(year) if base else None
    if base_dir:
        write_normalized_dataset(base_dir, year)
    return DraftClassETLSpec(
        draft_year=year,
        enabled=True,
        base_dir=base_dir,
        nhl_draft_json=None,
        hockeydb_draft_html=None,
        hockeydb_player_pages_dir=None,
        eliteprospects_csv=None,
        match_map=None,
        output_dir=tmp_path / "processed" / str(year),
    )


def test_manifest_loads_relative_paths_and_filters_years(tmp_path):
    manifest = tmp_path / "classes.csv"
    write_manifest(
        manifest,
        [
            {"draft_year": "2014", "enabled": "true", "base_dir": "base/2014"},
            {"draft_year": "2015", "enabled": "false", "base_dir": "base/2015"},
            {"draft_year": "2016", "enabled": "yes", "base_dir": "base/2016"},
        ],
    )

    specs = load_draft_class_manifest(manifest, project_root=tmp_path)
    selected = filter_draft_class_specs(specs, start_year=2015, end_year=2016)

    assert [item.draft_year for item in selected] == [2015, 2016]
    assert specs[0].base_dir == tmp_path / "base" / "2014"
    assert specs[1].enabled is False
    assert specs[2].output_dir == tmp_path / "data" / "processed" / "draft_classes" / "2016"


def test_plan_distinguishes_blocked_base_from_optional_enrichment(tmp_path):
    blocked = spec(tmp_path, 2020, base=False)
    plan = plan_draft_class(blocked)

    assert plan.status == "blocked"
    assert plan.base_source == "missing"
    assert plan.enrichment_status == "not_configured"


def test_range_runner_completes_ready_class_and_resumes(tmp_path):
    draft_spec = spec(tmp_path, 2019)
    calls: list[int] = []

    def executor(item: DraftClassETLSpec) -> None:
        calls.append(item.draft_year)
        write_normalized_dataset(item.output_dir / "final", item.draft_year)

    first = run_draft_range_etl(
        [draft_spec],
        executor=executor,
        report_dir=tmp_path / "reports",
    )
    second = run_draft_range_etl(
        [draft_spec],
        executor=executor,
        report_dir=tmp_path / "reports",
    )

    assert first.results[0].status == "completed"
    assert second.results[0].status == "skipped_complete"
    assert calls == [2019]
    assert (tmp_path / "reports" / "draft_class_runs.json").is_file()
    assert (draft_spec.output_dir / "etl_state.json").is_file()


def test_new_enrichment_file_invalidates_completed_state(tmp_path):
    draft_spec = spec(tmp_path, 2019)

    def executor(item: DraftClassETLSpec) -> None:
        write_normalized_dataset(item.output_dir / "final", item.draft_year)

    run_draft_range_etl([draft_spec], executor=executor, report_dir=tmp_path / "reports")
    eliteprospects_csv = tmp_path / "eliteprospects.csv"
    eliteprospects_csv.write_text("Player\nExample\n", encoding="utf-8")
    changed = replace(draft_spec, eliteprospects_csv=eliteprospects_csv)

    report = run_draft_range_etl(
        [changed],
        executor=executor,
        report_dir=tmp_path / "reports",
        dry_run=True,
    )

    assert report.results[0].status == "ready"
    assert report.results[0].enrichment_status == "eliteprospects_ready"


def test_range_runner_records_failure_and_continues(tmp_path):
    specs = [spec(tmp_path, 2019), spec(tmp_path, 2020)]

    def executor(item: DraftClassETLSpec) -> None:
        if item.draft_year == 2019:
            raise RuntimeError("fixture failure")
        write_normalized_dataset(item.output_dir / "final", item.draft_year)

    report = run_draft_range_etl(
        specs,
        executor=executor,
        report_dir=tmp_path / "reports",
    )

    assert [result.status for result in report.results] == ["failed", "completed"]
    assert "fixture failure" in report.results[0].detail
    assert report.failed_count == 1


def test_year_filter_rejects_inverted_range(tmp_path):
    with pytest.raises(ValueError, match="start_year"):
        filter_draft_class_specs([spec(tmp_path, 2019)], start_year=2020, end_year=2019)


def test_dataset_audit_rejects_mismatched_player_ids(tmp_path):
    dataset = tmp_path / "final"
    write_normalized_dataset(dataset)
    (dataset / "draft_selections.csv").write_text(
        "player_id,draft_year,team_id,round_number,overall_pick,source\n"
        "p2,2019,TST,1,1,fixture\n",
        encoding="utf-8",
    )

    audit = audit_normalized_dataset(dataset, 2019)

    assert audit.passed is False
    assert "different player IDs" in "; ".join(audit.issues)


def test_dataset_audit_rejects_truncated_full_class(tmp_path):
    dataset = tmp_path / "final"
    write_normalized_dataset(dataset)
    (dataset / "players.csv").write_text(
        "player_id,name,position,source\np1,Player One,C,fixture\n",
        encoding="utf-8",
    )

    audit = audit_normalized_dataset(dataset, 2019)

    assert audit.passed is False
    assert "outside plausible full-class range" in "; ".join(audit.issues)
