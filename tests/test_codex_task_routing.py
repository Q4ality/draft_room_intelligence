import csv

from draft_room_intelligence.reports.codex_task_routing import write_codex_task_routing_report


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def context_route_row(route_id="codex-routing"):
    return {
        "route_id": route_id,
        "route_name": "Codex routing",
        "trigger": "routing",
        "primary_docs": "AGENTS.md",
        "source_paths": ".codex/config.toml",
        "validation_commands": "python3 -m compileall src",
        "max_context_items": "4",
        "notes": "route",
    }


def task_rule_row(**overrides):
    row = {
        "task_id": "small-edit",
        "task_name": "Small edit",
        "trigger": "small change",
        "recommended_context_route": "codex-routing",
        "recommended_agent": "main",
        "reasoning_effort": "medium",
        "risk_level": "low",
        "validation_command": "git diff --check",
        "measurement_task_id": "route-small-edit",
        "notes": "main flow",
    }
    row.update(overrides)
    return row


def test_write_codex_task_routing_report_passes_valid_rules(tmp_path):
    context_routes = tmp_path / "context_routes.csv"
    task_routes = tmp_path / "task_routes.csv"
    write_rows(context_routes, [context_route_row()])
    write_rows(task_routes, [task_rule_row()])

    report = write_codex_task_routing_report(task_routes, context_routes, tmp_path / "report")

    assert report.passed
    assert report.failed_count == 0
    rows = list(csv.DictReader((tmp_path / "report" / "task_routing.csv").open()))
    assert rows[0]["status"] == "pass"


def test_write_codex_task_routing_report_fails_unknown_context_route(tmp_path):
    context_routes = tmp_path / "context_routes.csv"
    task_routes = tmp_path / "task_routes.csv"
    write_rows(context_routes, [context_route_row()])
    write_rows(task_routes, [task_rule_row(recommended_context_route="missing")])

    report = write_codex_task_routing_report(task_routes, context_routes, tmp_path / "report")

    assert not report.passed
    row = list(csv.DictReader((tmp_path / "report" / "task_routing.csv").open()))[0]
    assert row["status"] == "fail"
    assert "unknown context route" in row["issues"]


def test_write_codex_task_routing_report_requires_reviewer_for_high_risk(tmp_path):
    context_routes = tmp_path / "context_routes.csv"
    task_routes = tmp_path / "task_routes.csv"
    write_rows(context_routes, [context_route_row()])
    write_rows(task_routes, [task_rule_row(risk_level="high", recommended_agent="main")])

    report = write_codex_task_routing_report(task_routes, context_routes, tmp_path / "report")

    assert not report.passed
    row = list(csv.DictReader((tmp_path / "report" / "task_routing.csv").open()))[0]
    assert "high-risk task should use reviewer" in row["issues"]
