import csv
import json

from draft_room_intelligence.data.nhl_contracts import file_sha256
from draft_room_intelligence.data.roster_snapshots import NHL_TEAM_IDS
from draft_room_intelligence.reports.ingestion_plan import (
    source_access_cache_status,
    write_ingestion_plan_report,
)


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_write_ingestion_plan_report_classifies_source_families(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "data/raw/source_a").mkdir(parents=True)
    (project / "outputs/source_a").mkdir(parents=True)
    (project / "docs").mkdir()
    (project / "tests").mkdir()
    (project / "docs/source_a.md").write_text("# Source A\n", encoding="utf-8")
    (project / "tests/test_source_a.py").write_text("def test_source_a():\n    assert True\n", encoding="utf-8")
    manifest = project / "manifest.csv"
    write_rows(
        manifest,
        [
            {
                "source_family": "source_a",
                "priority": "1",
                "draft_years": "2025",
                "raw_cache_path": "data/raw/source_a",
                "normalized_output_path": "outputs/source_a",
                "doc_path": "docs/source_a.md",
                "test_path": "tests/test_source_a.py",
                "owner_stage": "adapter",
                "notes": "ready fixture",
            },
            {
                "source_family": "source_b",
                "priority": "2",
                "draft_years": "2026",
                "raw_cache_path": "data/raw/source_b",
                "normalized_output_path": "outputs/source_b",
                "doc_path": "docs/source_b.md",
                "test_path": "tests/test_source_b.py",
                "owner_stage": "collect",
                "notes": "missing fixture",
            },
        ],
    )

    report = write_ingestion_plan_report(manifest, tmp_path / "audit", project_root=project)

    assert report.ready_count == 1
    assert report.blocked_count == 1
    rows = list(csv.DictReader((tmp_path / "audit" / "source_family_audit.csv").open()))
    assert rows[0]["source_family"] == "source_a"
    assert rows[0]["readiness"] == "ready"
    assert rows[1]["source_family"] == "source_b"
    assert rows[1]["readiness"] == "blocked"
    assert (tmp_path / "audit" / "summary.md").exists()


def test_ingestion_plan_requires_raw_cache_for_ready_status(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "outputs/source_a").mkdir(parents=True)
    (project / "docs").mkdir()
    (project / "tests").mkdir()
    (project / "docs/source_a.md").write_text("# Source A\n", encoding="utf-8")
    (project / "tests/test_source_a.py").write_text("def test_source_a():\n    assert True\n", encoding="utf-8")
    manifest = project / "manifest.csv"
    write_rows(
        manifest,
        [
            {
                "source_family": "source_a",
                "priority": "1",
                "draft_years": "2025",
                "raw_cache_path": "data/raw/source_a",
                "normalized_output_path": "outputs/source_a",
                "doc_path": "docs/source_a.md",
                "test_path": "tests/test_source_a.py",
                "owner_stage": "adapter",
                "notes": "normalized but no raw cache",
            },
        ],
    )

    report = write_ingestion_plan_report(manifest, tmp_path / "audit", project_root=project)

    assert report.ready_count == 0
    row = list(csv.DictReader((tmp_path / "audit" / "source_family_audit.csv").open()))[0]
    assert row["readiness"] == "partial"
    assert row["next_action"] == "Stage cached raw inputs so this source can rerun without curated/manual files."


def test_ingestion_plan_preserves_source_access_blocker(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "docs").mkdir()
    (project / "tests").mkdir()
    (project / "docs/contracts.md").write_text("# Contracts\n", encoding="utf-8")
    (project / "tests/test_contracts.py").write_text(
        "def test_contracts():\n    assert True\n", encoding="utf-8"
    )
    manifest = project / "manifest.csv"
    write_rows(
        manifest,
        [
            {
                "source_family": "nhl_contracts",
                "priority": "1",
                "draft_years": "2025",
                "raw_cache_path": "data/raw/contracts/2025-06-01",
                "normalized_output_path": "outputs/contracts.csv",
                "doc_path": "docs/contracts.md",
                "test_path": "tests/test_contracts.py",
                "owner_stage": "source_access",
                "notes": "permitted snapshot required",
            }
        ],
    )

    report = write_ingestion_plan_report(manifest, tmp_path / "audit", project_root=project)
    row = report.audits[0].to_row()

    assert row["readiness"] == "blocked"
    assert row["next_action"] == (
        "Obtain a permitted dated export or API credential; "
        "do not substitute current web tables."
    )

    (project / "data/raw/contracts/2025-06-01").mkdir(parents=True)
    (project / "outputs").mkdir()
    (project / "outputs/contracts.csv").write_text("stale\n", encoding="utf-8")
    report = write_ingestion_plan_report(manifest, tmp_path / "audit-empty", project_root=project)

    assert report.audits[0].readiness == "blocked"
    assert report.audits[0].raw_cache_status == "missing"

    raw_csv = project / "data/raw/contracts/2025-06-01/source.csv"
    raw_csv.write_text("Team,Player,AAV,End\n", encoding="utf-8")
    raw_csv.with_suffix(".metadata.json").write_text("{}", encoding="utf-8")
    report = write_ingestion_plan_report(manifest, tmp_path / "audit-invalid", project_root=project)

    assert report.audits[0].readiness == "blocked"
    assert report.audits[0].raw_cache_status == "missing"

    raw_csv.write_text("Team,Player,AAV,End\nNYI,Example,$1000000,2026\n", encoding="utf-8")
    valid_metadata = {
        "source": "licensed-export",
        "source_url": "https://example.test/export",
        "snapshot_date": "2025-06-01",
        "retrieved_at": "2026-07-21",
        "access_basis": "licensed API export",
        "input_sha256": file_sha256(raw_csv),
    }
    for invalid_metadata in (
        {**valid_metadata, "source": None},
        {**valid_metadata, "input_sha256": 123},
    ):
        raw_csv.with_suffix(".metadata.json").write_text(
            json.dumps(invalid_metadata), encoding="utf-8"
        )
        report = write_ingestion_plan_report(manifest, tmp_path / "audit-wrong-type", project_root=project)
        assert report.audits[0].raw_cache_status == "missing"

    raw_csv.with_suffix(".metadata.json").write_text(json.dumps(valid_metadata), encoding="utf-8")
    report = write_ingestion_plan_report(manifest, tmp_path / "audit-valid", project_root=project)

    assert report.audits[0].readiness == "ready"
    assert report.audits[0].raw_cache_status == "present"


def test_roster_source_access_requires_rights_snapshot_scope(tmp_path):
    cache = tmp_path / "2025-06-01"
    cache.mkdir()
    raw_csv = cache / "rights.csv"
    roster_rows = [
        {
            "team": team_id,
            "player": f"{team_id} Player {index}",
            "pos": "D",
            "level": "PROSPECT",
            "status": "reserve_list",
        }
        for team_id in sorted(NHL_TEAM_IDS)
        for index in range(15)
    ]
    write_rows(raw_csv, roster_rows)
    metadata = {
        "source": "licensed-export",
        "source_url": "https://example.test/export",
        "snapshot_date": "2025-06-01",
        "retrieved_at": "2026-07-21",
        "access_basis": "licensed API export",
        "scope": "sample",
        "input_sha256": file_sha256(raw_csv),
    }
    raw_csv.with_suffix(".metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    assert source_access_cache_status(cache, source_family="team_rosters") == "missing"

    metadata["scope"] = "full_league_rights_snapshot"
    raw_csv.with_suffix(".metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    assert source_access_cache_status(cache, source_family="team_rosters") == "present"
