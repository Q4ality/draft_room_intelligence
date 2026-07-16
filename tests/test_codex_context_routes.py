import csv

from draft_room_intelligence.reports.codex_context_routes import write_codex_context_routes_report


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def route_row(**overrides):
    row = {
        "route_id": "demo",
        "route_name": "Demo",
        "trigger": "Demo question",
        "primary_docs": "docs/demo.md",
        "source_paths": "src/demo.py;tests/test_demo.py",
        "validation_commands": "python3 -m compileall src",
        "max_context_items": "4",
        "notes": "bounded route",
    }
    row.update(overrides)
    return row


def create_route_project(root):
    (root / "docs").mkdir()
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "docs/demo.md").write_text("# Demo\n", encoding="utf-8")
    (root / "src/demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests/test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")


def test_write_codex_context_routes_report_passes_bounded_existing_paths(tmp_path):
    create_route_project(tmp_path)
    manifest = tmp_path / "routes.csv"
    write_rows(manifest, [route_row()])

    report = write_codex_context_routes_report(manifest, tmp_path / "report", project_root=tmp_path)

    assert report.passed
    assert report.failed_count == 0
    assert (tmp_path / "report" / "summary.md").exists()
    rows = list(csv.DictReader((tmp_path / "report" / "context_routes.csv").open()))
    assert rows[0]["context_item_count"] == "3"


def test_write_codex_context_routes_report_fails_missing_path(tmp_path):
    create_route_project(tmp_path)
    manifest = tmp_path / "routes.csv"
    write_rows(manifest, [route_row(source_paths="src/missing.py")])

    report = write_codex_context_routes_report(manifest, tmp_path / "report", project_root=tmp_path)

    assert not report.passed
    row = list(csv.DictReader((tmp_path / "report" / "context_routes.csv").open()))[0]
    assert row["status"] == "fail"
    assert row["missing_paths"] == "src/missing.py"


def test_write_codex_context_routes_report_fails_when_route_is_too_large(tmp_path):
    create_route_project(tmp_path)
    manifest = tmp_path / "routes.csv"
    write_rows(manifest, [route_row(max_context_items="2")])

    report = write_codex_context_routes_report(manifest, tmp_path / "report", project_root=tmp_path)

    assert not report.passed
    row = list(csv.DictReader((tmp_path / "report" / "context_routes.csv").open()))[0]
    assert row["status"] == "fail"
    assert "Reduce route paths" in row["next_action"]
