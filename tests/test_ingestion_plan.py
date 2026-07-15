import csv

from draft_room_intelligence.reports.ingestion_plan import write_ingestion_plan_report


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
