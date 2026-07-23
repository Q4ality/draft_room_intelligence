import csv
import json
import subprocess

from draft_room_intelligence.reports.codex_dispatch import (
    build_codex_dispatch,
    route_for_phase,
    run_codex_dispatch,
    select_task_routing_rule,
)
from draft_room_intelligence.reports.codex_task_routing import TaskRoutingRule


def routing_rule(
    *,
    task_id="usage-measurement",
    task_name="Codex usage measurement",
    trigger="Token consumption dashboard benchmark route measurement",
    model="gpt-5.6-luna",
    reasoning="medium",
):
    return TaskRoutingRule(
        task_id=task_id,
        task_name=task_name,
        trigger=trigger,
        recommended_context_route="codex-routing",
        recommended_agent="main",
        recommended_model=model,
        reasoning_effort=reasoning,
        risk_level="medium",
        validation_command="git diff --check",
        measurement_task_id=f"route-{task_id}",
        notes="test",
    )


def write_manifest(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_select_task_routing_rule_matches_task_words():
    rules = [
        routing_rule(),
        routing_rule(
            task_id="demo-update",
            task_name="Demo readiness update",
            trigger="Demo export site player detail",
            model="gpt-5.6-terra",
        ),
    ]

    selected = select_task_routing_rule(rules, "Update the demo site player detail")

    assert selected.task_id == "demo-update"
    assert selected.recommended_model == "gpt-5.6-terra"


def test_select_task_routing_rule_supports_explicit_task_id():
    rules = [routing_rule(), routing_rule(task_id="small-edit")]

    selected = select_task_routing_rule(rules, "ambiguous task", task_id="small-edit")

    assert selected.task_id == "small-edit"


def test_build_codex_dispatch_enforces_model_and_reasoning(tmp_path):
    manifest = tmp_path / "routes.csv"
    write_manifest(manifest, [routing_rule().__dict__])

    dispatch = build_codex_dispatch(
        "Measure token consumption",
        manifest,
        project_root=tmp_path,
    )

    assert dispatch.command[:3] == ["codex", "exec", "--json"]
    assert ["--model", "gpt-5.6-luna"] == dispatch.command[3:5]
    assert 'model_reasoning_effort="medium"' in dispatch.command
    assert str(tmp_path.resolve()) in dispatch.command


def test_build_codex_dispatch_supports_baseline_overrides(tmp_path):
    manifest = tmp_path / "routes.csv"
    write_manifest(manifest, [routing_rule().__dict__])

    dispatch = build_codex_dispatch(
        "Measure token consumption",
        manifest,
        project_root=tmp_path,
        model="gpt-5.6-sol",
        reasoning_effort="medium",
    )

    assert dispatch.model == "gpt-5.6-sol"
    assert 'model_reasoning_effort="medium"' in dispatch.command


def test_high_risk_implementation_uses_terra_before_sol_review():
    rule = routing_rule(
        task_id="ingestion-change",
        model="gpt-5.6-sol",
        reasoning="high",
    )
    rule = TaskRoutingRule(
        **{
            **rule.__dict__,
            "risk_level": "high",
            "recommended_agent": "reviewer",
        }
    )

    implementation = route_for_phase(rule, "implementation")
    review = route_for_phase(rule, "review")

    assert implementation.model == "gpt-5.6-terra"
    assert implementation.reasoning_effort == "medium"
    assert implementation.agent == "main"
    assert review.model == "gpt-5.6-sol"
    assert review.reasoning_effort == "high"
    assert review.agent == "reviewer"


def test_discovery_and_validation_use_lower_cost_phase_routes():
    rule = routing_rule(model="gpt-5.6-sol", reasoning="high")

    discovery = route_for_phase(rule, "discovery")
    validation = route_for_phase(rule, "validation")

    assert (discovery.model, discovery.reasoning_effort, discovery.agent) == (
        "gpt-5.6-terra",
        "low",
        "kb_explorer",
    )
    assert (validation.model, validation.reasoning_effort, validation.agent) == (
        "gpt-5.6-luna",
        "low",
        "main",
    )


def test_dispatch_reports_selected_phase(tmp_path):
    manifest = tmp_path / "routes.csv"
    write_manifest(
        manifest,
        [
            {
                **routing_rule(
                    task_id="ingestion-change",
                    model="gpt-5.6-sol",
                    reasoning="high",
                ).__dict__,
                "risk_level": "high",
                "recommended_agent": "reviewer",
            }
        ],
    )

    dispatch = build_codex_dispatch(
        "Fix parser source coverage",
        manifest,
        project_root=tmp_path,
        task_id="ingestion-change",
        phase="implementation",
    )

    assert dispatch.phase == "implementation"
    assert dispatch.model == "gpt-5.6-terra"
    assert dispatch.to_dict()["agent"] == "main"
    assert "Phase: implementation" in dispatch.command[-1]


def test_run_codex_dispatch_records_exact_usage(monkeypatch, tmp_path):
    manifest = tmp_path / "routes.csv"
    write_manifest(manifest, [routing_rule().__dict__])
    dispatch = build_codex_dispatch(
        "Measure token consumption",
        manifest,
        project_root=tmp_path,
    )
    events = [
        {"type": "thread.started", "thread_id": "thread-123"},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "Done."},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 120,
                "cached_input_tokens": 20,
                "output_tokens": 10,
            },
        },
    ]
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="\n".join(json.dumps(event) for event in events),
            stderr="",
        ),
    )
    run_log = tmp_path / "usage" / "run_log.csv"

    result = run_codex_dispatch(dispatch, run_log_csv=run_log)
    run = result.usage_run

    assert run.run_id == "thread-123"
    assert result.response == "Done."
    assert run.exact_input_tokens == 100
    assert run.exact_cached_input_tokens == 20
    assert run.exact_output_tokens == 10
    rows = list(csv.DictReader(run_log.open(encoding="utf-8")))
    assert rows[0]["model"] == "gpt-5.6-luna"
    assert rows[0]["variant"] == "routed"
