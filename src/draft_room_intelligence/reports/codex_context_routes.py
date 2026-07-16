"""Audit compact Codex context routes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROUTE_COLUMNS = [
    "route_id",
    "route_name",
    "trigger",
    "primary_docs",
    "source_paths",
    "validation_commands",
    "max_context_items",
    "notes",
]

AUDIT_COLUMNS = [
    *ROUTE_COLUMNS,
    "context_item_count",
    "missing_paths",
    "status",
    "next_action",
]


@dataclass(frozen=True)
class ContextRoute:
    route_id: str
    route_name: str
    trigger: str
    primary_docs: str
    source_paths: str
    validation_commands: str
    max_context_items: int
    notes: str

    @property
    def docs(self) -> list[str]:
        return split_items(self.primary_docs)

    @property
    def sources(self) -> list[str]:
        return split_items(self.source_paths)

    @property
    def context_item_count(self) -> int:
        return len(self.docs) + len(self.sources)


@dataclass(frozen=True)
class ContextRouteAudit:
    route: ContextRoute
    missing_paths: list[str]
    status: str
    next_action: str

    def to_row(self) -> dict[str, str]:
        return {
            "route_id": self.route.route_id,
            "route_name": self.route.route_name,
            "trigger": self.route.trigger,
            "primary_docs": self.route.primary_docs,
            "source_paths": self.route.source_paths,
            "validation_commands": self.route.validation_commands,
            "max_context_items": str(self.route.max_context_items),
            "notes": self.route.notes,
            "context_item_count": str(self.route.context_item_count),
            "missing_paths": ";".join(self.missing_paths),
            "status": self.status,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class ContextRouteReport:
    manifest_path: Path
    audits: list[ContextRouteAudit]

    @property
    def passed(self) -> bool:
        return all(audit.status == "pass" for audit in self.audits)

    @property
    def failed_count(self) -> int:
        return sum(1 for audit in self.audits if audit.status != "pass")


def write_codex_context_routes_report(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    project_root: str | Path = ".",
) -> ContextRouteReport:
    report = build_codex_context_routes_report(manifest_path, project_root=project_root)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_csv(root / "context_routes.csv", AUDIT_COLUMNS, [audit.to_row() for audit in report.audits])
    (root / "summary.md").write_text(format_context_routes_report(report), encoding="utf-8")
    return report


def build_codex_context_routes_report(
    manifest_path: str | Path,
    *,
    project_root: str | Path = ".",
) -> ContextRouteReport:
    manifest = Path(manifest_path)
    root = Path(project_root)
    audits = [audit_context_route(route, root) for route in load_context_routes(manifest)]
    return ContextRouteReport(manifest_path=manifest, audits=audits)


def load_context_routes(path: Path) -> list[ContextRoute]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        ContextRoute(
            route_id=row.get("route_id", ""),
            route_name=row.get("route_name", ""),
            trigger=row.get("trigger", ""),
            primary_docs=row.get("primary_docs", ""),
            source_paths=row.get("source_paths", ""),
            validation_commands=row.get("validation_commands", ""),
            max_context_items=int_value(row.get("max_context_items")),
            notes=row.get("notes", ""),
        )
        for row in rows
        if row.get("route_id")
    ]


def audit_context_route(route: ContextRoute, project_root: Path) -> ContextRouteAudit:
    missing = [
        item
        for item in [*route.docs, *route.sources]
        if not route_path_exists(project_root, item)
    ]
    if missing:
        return ContextRouteAudit(
            route=route,
            missing_paths=missing,
            status="fail",
            next_action="Update the route or add the missing path before relying on this context pack.",
        )
    if route.context_item_count > route.max_context_items:
        return ContextRouteAudit(
            route=route,
            missing_paths=[],
            status="fail",
            next_action="Reduce route paths or raise max_context_items with an explicit reason.",
        )
    if not route.validation_commands.strip():
        return ContextRouteAudit(
            route=route,
            missing_paths=[],
            status="fail",
            next_action="Add at least one validation command for this route.",
        )
    return ContextRouteAudit(
        route=route,
        missing_paths=[],
        status="pass",
        next_action="Use this route as the bounded context pack for matching tasks.",
    )


def format_context_routes_report(report: ContextRouteReport) -> str:
    lines = [
        "# Codex Context Routes",
        "",
        f"- Manifest: `{report.manifest_path}`",
        f"- Routes: {len(report.audits)}",
        f"- Status: {'pass' if report.passed else 'fail'}",
        f"- Failed: {report.failed_count}",
        "",
        "| Route | Status | Items | Missing | Next action |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for audit in report.audits:
        missing = ", ".join(audit.missing_paths) if audit.missing_paths else ""
        lines.append(
            f"| {audit.route.route_name} | {audit.status} | {audit.route.context_item_count}/{audit.route.max_context_items} | {missing} | {audit.next_action} |"
        )
    lines.extend(
        [
            "",
            "## Operating Rule",
            "",
            "Before broad repo exploration, choose the matching route and read only the listed docs/source paths unless the task proves they are insufficient.",
        ]
    )
    return "\n".join(lines) + "\n"


def route_path_exists(project_root: Path, route_path: str) -> bool:
    path = project_root / route_path
    return path.exists() or path.is_symlink()


def split_items(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def int_value(value: str | None) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
