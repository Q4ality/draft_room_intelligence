"""Audit project-scoped Codex routing setup."""

from __future__ import annotations

import csv
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

EXPECTED_SKILLS = [
    "prepare-draft-demo-data",
    "project-context",
    "validate-change",
    "debug-ingestion",
]

EXPECTED_AGENTS = [
    ("kb_explorer", ".codex/agents/kb-explorer.toml"),
    ("reviewer", ".codex/agents/reviewer.toml"),
]

CHECK_COLUMNS = ["check_id", "status", "detail", "path"]


@dataclass(frozen=True)
class RoutingCheck:
    check_id: str
    status: str
    detail: str
    path: str

    def to_row(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "detail": self.detail,
            "path": self.path,
        }


@dataclass(frozen=True)
class RoutingAuditReport:
    checks: list[RoutingCheck]

    @property
    def passed(self) -> bool:
        return all(check.status == "pass" for check in self.checks)

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.status != "pass")


def write_codex_routing_audit(project_root: str | Path, output_dir: str | Path) -> RoutingAuditReport:
    report = build_codex_routing_audit(project_root)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "checks.csv", CHECK_COLUMNS, [check.to_row() for check in report.checks])
    (root / "summary.md").write_text(format_codex_routing_audit(report), encoding="utf-8")
    return report


def build_codex_routing_audit(project_root: str | Path) -> RoutingAuditReport:
    root = Path(project_root)
    checks = [
        file_exists_check(root, "AGENTS.md", "repo guidance exists"),
        file_exists_check(root, "docs/codex_routing.md", "routing documentation exists"),
        file_exists_check(root, "docs/codex_usage_measurement.md", "usage measurement documentation exists"),
        file_exists_check(root, "data/reference/codex_context_routes.csv", "bounded context route manifest exists"),
        file_exists_check(root, "data/reference/codex_task_routing.csv", "task-level routing manifest exists"),
        config_check(root),
    ]
    checks.extend(agent_config_checks(root))
    checks.extend(skill_checks(root))
    return RoutingAuditReport(checks=checks)


def config_check(root: Path) -> RoutingCheck:
    path = ".codex/config.toml"
    config_path = root / path
    if not config_path.exists():
        return RoutingCheck("codex_config", "fail", "missing project Codex config", path)
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return RoutingCheck("codex_config", "fail", f"invalid TOML: {exc}", path)
    agents = config.get("agents", {})
    required = [
        ("model", "gpt-5.6-sol"),
        ("model_reasoning_effort", "medium"),
        ("plan_mode_reasoning_effort", "high"),
        ("model_verbosity", "low"),
        ("tool_output_token_limit", 6000),
    ]
    missing = [key for key, value in required if config.get(key) != value]
    if agents.get("max_threads") != 3:
        missing.append("agents.max_threads")
    if agents.get("max_depth") != 1:
        missing.append("agents.max_depth")
    for agent_name, _ in EXPECTED_AGENTS:
        if agent_name not in agents:
            missing.append(f"agents.{agent_name}")
    if missing:
        return RoutingCheck("codex_config", "fail", "unexpected or missing keys: " + ", ".join(missing), path)
    return RoutingCheck("codex_config", "pass", "project config has expected routing defaults", path)


def agent_config_checks(root: Path) -> list[RoutingCheck]:
    checks = []
    for agent_name, path in EXPECTED_AGENTS:
        full_path = root / path
        if not full_path.exists():
            checks.append(RoutingCheck(f"agent_{agent_name}", "fail", "missing custom agent config", path))
            continue
        try:
            config = tomllib.loads(full_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            checks.append(RoutingCheck(f"agent_{agent_name}", "fail", f"invalid TOML: {exc}", path))
            continue
        missing = [key for key in ["name", "description", "developer_instructions"] if not config.get(key)]
        if config.get("name") != agent_name:
            missing.append("name mismatch")
        if missing:
            checks.append(RoutingCheck(f"agent_{agent_name}", "fail", "missing fields: " + ", ".join(missing), path))
        else:
            checks.append(RoutingCheck(f"agent_{agent_name}", "pass", "custom agent config is present and valid", path))
    return checks


def skill_checks(root: Path) -> list[RoutingCheck]:
    checks = []
    for skill in EXPECTED_SKILLS:
        skill_path = root / "skills" / skill / "SKILL.md"
        link_path = root / ".agents" / "skills" / skill
        if not skill_path.exists():
            checks.append(RoutingCheck(f"skill_{skill}", "fail", "missing authored skill", str(skill_path.relative_to(root))))
            continue
        if not link_path.exists() and not link_path.is_symlink():
            checks.append(RoutingCheck(f"skill_{skill}", "fail", "missing .agents/skills discovery link", str(link_path.relative_to(root))))
            continue
        if not link_path.is_symlink():
            checks.append(RoutingCheck(f"skill_{skill}", "fail", "discovery path is not a symlink", str(link_path.relative_to(root))))
            continue
        target = os.readlink(link_path)
        expected_target = f"../../skills/{skill}"
        if target != expected_target:
            checks.append(
                RoutingCheck(
                    f"skill_{skill}",
                    "fail",
                    f"unexpected symlink target: {target}",
                    str(link_path.relative_to(root)),
                )
            )
            continue
        checks.append(RoutingCheck(f"skill_{skill}", "pass", "authored skill and discovery symlink are present", str(link_path.relative_to(root))))
    return checks


def file_exists_check(root: Path, path: str, detail: str) -> RoutingCheck:
    return RoutingCheck(
        check_id=path.replace("/", "_").replace(".", "_"),
        status="pass" if (root / path).exists() else "fail",
        detail=detail,
        path=path,
    )


def format_codex_routing_audit(report: RoutingAuditReport) -> str:
    lines = [
        "# Codex Routing Audit",
        "",
        f"- Status: {'pass' if report.passed else 'fail'}",
        f"- Checks: {len(report.checks)}",
        f"- Failed: {report.failed_count}",
        "",
        "| Check | Status | Detail | Path |",
        "| --- | --- | --- | --- |",
    ]
    for check in report.checks:
        lines.append(f"| {check.check_id} | {check.status} | {check.detail} | `{check.path}` |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
