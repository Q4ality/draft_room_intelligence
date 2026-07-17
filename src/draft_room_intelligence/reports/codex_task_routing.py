"""Audit task-level Codex routing recommendations."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.reports.codex_context_routes import load_context_routes


ROUTING_COLUMNS = [
    "task_id",
    "task_name",
    "trigger",
    "recommended_context_route",
    "recommended_agent",
    "recommended_model",
    "reasoning_effort",
    "risk_level",
    "validation_command",
    "measurement_task_id",
    "notes",
]

AUDIT_COLUMNS = [
    *ROUTING_COLUMNS,
    "status",
    "issues",
    "next_action",
]

ALLOWED_AGENTS = {"main", "kb_explorer", "reviewer"}
ALLOWED_MODELS = {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}
ALLOWED_REASONING = {"low", "medium", "high"}
ALLOWED_RISK = {"low", "medium", "high"}


@dataclass(frozen=True)
class TaskRoutingRule:
    task_id: str
    task_name: str
    trigger: str
    recommended_context_route: str
    recommended_agent: str
    recommended_model: str
    reasoning_effort: str
    risk_level: str
    validation_command: str
    measurement_task_id: str
    notes: str


@dataclass(frozen=True)
class TaskRoutingAudit:
    rule: TaskRoutingRule
    issues: list[str]

    @property
    def status(self) -> str:
        return "fail" if self.issues else "pass"

    @property
    def next_action(self) -> str:
        if self.issues:
            return "Fix the routing rule before using it for task dispatch."
        if self.rule.recommended_agent == "reviewer":
            return "Use the context route first, implement, then request reviewer validation."
        if self.rule.recommended_agent == "kb_explorer":
            return "Use read-only exploration only when the bounded context route is insufficient."
        return "Use the main flow with the listed context route and validation command."

    def to_row(self) -> dict[str, str]:
        return {
            "task_id": self.rule.task_id,
            "task_name": self.rule.task_name,
            "trigger": self.rule.trigger,
            "recommended_context_route": self.rule.recommended_context_route,
            "recommended_agent": self.rule.recommended_agent,
            "recommended_model": self.rule.recommended_model,
            "reasoning_effort": self.rule.reasoning_effort,
            "risk_level": self.rule.risk_level,
            "validation_command": self.rule.validation_command,
            "measurement_task_id": self.rule.measurement_task_id,
            "notes": self.rule.notes,
            "status": self.status,
            "issues": ";".join(self.issues),
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class TaskRoutingReport:
    manifest_path: Path
    context_routes_path: Path
    audits: list[TaskRoutingAudit]

    @property
    def passed(self) -> bool:
        return all(audit.status == "pass" for audit in self.audits)

    @property
    def failed_count(self) -> int:
        return sum(1 for audit in self.audits if audit.status != "pass")


def write_codex_task_routing_report(
    manifest_path: str | Path,
    context_routes_path: str | Path,
    output_dir: str | Path,
) -> TaskRoutingReport:
    report = build_codex_task_routing_report(manifest_path, context_routes_path)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "task_routing.csv", AUDIT_COLUMNS, [audit.to_row() for audit in report.audits])
    (root / "summary.md").write_text(format_task_routing_report(report), encoding="utf-8")
    return report


def build_codex_task_routing_report(
    manifest_path: str | Path,
    context_routes_path: str | Path,
) -> TaskRoutingReport:
    route_ids = {route.route_id for route in load_context_routes(Path(context_routes_path))}
    audits = [audit_task_routing_rule(rule, route_ids) for rule in load_task_routing_rules(Path(manifest_path))]
    return TaskRoutingReport(
        manifest_path=Path(manifest_path),
        context_routes_path=Path(context_routes_path),
        audits=audits,
    )


def load_task_routing_rules(path: Path) -> list[TaskRoutingRule]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        TaskRoutingRule(
            task_id=row.get("task_id", ""),
            task_name=row.get("task_name", ""),
            trigger=row.get("trigger", ""),
            recommended_context_route=row.get("recommended_context_route", ""),
            recommended_agent=row.get("recommended_agent", ""),
            recommended_model=row.get("recommended_model", ""),
            reasoning_effort=row.get("reasoning_effort", ""),
            risk_level=row.get("risk_level", ""),
            validation_command=row.get("validation_command", ""),
            measurement_task_id=row.get("measurement_task_id", ""),
            notes=row.get("notes", ""),
        )
        for row in rows
        if row.get("task_id")
    ]


def audit_task_routing_rule(rule: TaskRoutingRule, route_ids: set[str]) -> TaskRoutingAudit:
    issues = []
    if rule.recommended_context_route not in route_ids:
        issues.append(f"unknown context route: {rule.recommended_context_route}")
    if rule.recommended_agent not in ALLOWED_AGENTS:
        issues.append(f"unknown agent: {rule.recommended_agent}")
    if rule.recommended_model not in ALLOWED_MODELS:
        issues.append(f"unknown model: {rule.recommended_model}")
    if rule.reasoning_effort not in ALLOWED_REASONING:
        issues.append(f"unknown reasoning effort: {rule.reasoning_effort}")
    if rule.risk_level not in ALLOWED_RISK:
        issues.append(f"unknown risk level: {rule.risk_level}")
    if not rule.validation_command.strip():
        issues.append("missing validation command")
    if not rule.measurement_task_id.strip():
        issues.append("missing measurement task id")
    if rule.risk_level == "high" and rule.recommended_agent != "reviewer":
        issues.append("high-risk task should use reviewer")
    if rule.risk_level == "high" and rule.recommended_model != "gpt-5.6-sol":
        issues.append("high-risk task should use gpt-5.6-sol")
    if rule.recommended_agent == "reviewer" and rule.reasoning_effort != "high":
        issues.append("reviewer task should use high reasoning")
    if rule.recommended_agent == "reviewer" and rule.recommended_model != "gpt-5.6-sol":
        issues.append("reviewer task should use gpt-5.6-sol")
    return TaskRoutingAudit(rule=rule, issues=issues)


def format_task_routing_report(report: TaskRoutingReport) -> str:
    lines = [
        "# Codex Task Routing",
        "",
        f"- Manifest: `{report.manifest_path}`",
        f"- Context routes: `{report.context_routes_path}`",
        f"- Rules: {len(report.audits)}",
        f"- Status: {'pass' if report.passed else 'fail'}",
        f"- Failed: {report.failed_count}",
        "",
        "| Task | Route | Agent | Model | Reasoning | Risk | Status | Next action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for audit in report.audits:
        lines.append(
            "| {task} | {route} | {agent} | {model} | {reasoning} | {risk} | {status} | {next_action} |".format(
                task=audit.rule.task_name,
                route=audit.rule.recommended_context_route,
                agent=audit.rule.recommended_agent,
                model=audit.rule.recommended_model,
                reasoning=audit.rule.reasoning_effort,
                risk=audit.rule.risk_level,
                status=audit.status,
                next_action=audit.next_action,
            )
        )
    lines.extend(
        [
            "",
            "## Dispatch Rule",
            "",
            "Choose the closest task rule, read its context route, use the recommended model, and use the recommended agent only when the risk and discovery need justify the extra context.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
