"""Helpers for scaffolding and auditing a single-class demo dataset."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DemoClassPaths:
    draft_year: int
    project_root: Path

    @property
    def hockeydb_dir(self) -> Path:
        return self.project_root / "data" / "raw" / "hockeydb" / str(self.draft_year)

    @property
    def hockeydb_draft_html(self) -> Path:
        return self.hockeydb_dir / f"nhl{self.draft_year}e.html"

    @property
    def hockeydb_player_pages_dir(self) -> Path:
        return self.hockeydb_dir / "player_pages"

    @property
    def eliteprospects_csv(self) -> Path:
        return self.project_root / "data" / "raw" / f"eliteprospects_{self.draft_year}.csv"

    @property
    def match_map_csv(self) -> Path:
        return self.project_root / "data" / "reference" / f"eliteprospects_{self.draft_year}_match_map.csv"

    @property
    def featured_players_csv(self) -> Path:
        return self.project_root / "data" / "reference" / f"demo_{self.draft_year}_featured_players.csv"

    @property
    def processed_demo_dir(self) -> Path:
        return self.project_root / "data" / "processed" / f"demo_{self.draft_year}"

    @property
    def outputs_dir(self) -> Path:
        return self.project_root / "outputs" / f"demo_{self.draft_year}"


@dataclass(frozen=True)
class DemoAuditItem:
    label: str
    path: Path
    status: str
    detail: str


@dataclass(frozen=True)
class DemoAuditReport:
    draft_year: int
    paths: DemoClassPaths
    items: list[DemoAuditItem]

    @property
    def ready_for_etl(self) -> bool:
        return all(
            item.status == "present"
            for item in self.items
            if item.label in {"HockeyDB draft HTML"}
        )

    @property
    def strong_for_demo(self) -> bool:
        required = {
            "HockeyDB draft HTML",
            "HockeyDB player pages",
            "Elite Prospects export",
            "Featured players template",
        }
        return all(item.status == "present" for item in self.items if item.label in required)

    @property
    def missing_required_items(self) -> list[DemoAuditItem]:
        required = {
            "HockeyDB draft HTML",
            "HockeyDB player pages",
            "Elite Prospects export",
            "Featured players template",
        }
        return [item for item in self.items if item.label in required and item.status != "present"]

    @property
    def next_step(self) -> str:
        if not self.ready_for_etl:
            return "Collect the required raw inputs, then re-run the audit."
        if not self.strong_for_demo:
            return "Add richer player pages and Elite Prospects coverage, then build the ETL snapshot."
        return "Run ETL and build the demo package/site."


def demo_class_paths(project_root: str | Path, draft_year: int) -> DemoClassPaths:
    return DemoClassPaths(draft_year=draft_year, project_root=Path(project_root))


def scaffold_demo_class(project_root: str | Path, draft_year: int) -> DemoClassPaths:
    paths = demo_class_paths(project_root, draft_year)
    paths.hockeydb_player_pages_dir.mkdir(parents=True, exist_ok=True)
    paths.processed_demo_dir.mkdir(parents=True, exist_ok=True)
    paths.outputs_dir.mkdir(parents=True, exist_ok=True)
    paths.match_map_csv.parent.mkdir(parents=True, exist_ok=True)
    _write_csv_if_missing(
        paths.match_map_csv,
        ["source_player_id", "base_player_id", "note"],
        [],
    )
    _write_csv_if_missing(
        paths.featured_players_csv,
        [
            "player_id",
            "player_name",
            "demo_role",
            "story_hook",
            "priority",
            "notes",
        ],
        [],
    )
    return paths


def audit_demo_class(project_root: str | Path, draft_year: int) -> DemoAuditReport:
    paths = demo_class_paths(project_root, draft_year)
    items = [
        _audit_file("HockeyDB draft HTML", paths.hockeydb_draft_html),
        _audit_dir("HockeyDB player pages", paths.hockeydb_player_pages_dir, "*.html"),
        _audit_file("Elite Prospects export", paths.eliteprospects_csv),
        _audit_file("Reviewed EP match map", paths.match_map_csv, optional=True),
        _audit_file("Featured players template", paths.featured_players_csv),
        _audit_dir("Processed demo dataset", paths.processed_demo_dir, "*.csv", optional=True),
        _audit_dir("Demo outputs", paths.outputs_dir, "*", optional=True),
    ]
    return DemoAuditReport(draft_year=draft_year, paths=paths, items=items)


def format_demo_audit_report(report: DemoAuditReport) -> str:
    lines = [
        f"# Demo Class Audit: {report.draft_year}",
        f"Ready for ETL: {'yes' if report.ready_for_etl else 'no'}",
        f"Strong for demo: {'yes' if report.strong_for_demo else 'no'}",
        f"Next step: {report.next_step}",
        "",
    ]
    for item in report.items:
        lines.append(f"- {item.label}: {item.status} ({item.detail})")
    if report.missing_required_items:
        lines.extend(
            [
                "",
                "## Missing Required Inputs",
            ]
        )
        for item in report.missing_required_items:
            lines.append(f"- {item.label}: {item.path}")
    lines.extend(
        [
            "",
            "## Commands",
            _etl_command(report.paths, include_eliteprospects=False),
            _etl_command(report.paths, include_eliteprospects=True),
            _demo_site_command(report.paths),
        ]
    )
    return "\n".join(lines)


def _audit_file(label: str, path: Path, optional: bool = False) -> DemoAuditItem:
    if path.exists() and path.is_file():
        return DemoAuditItem(label=label, path=path, status="present", detail=str(path))
    if optional:
        return DemoAuditItem(label=label, path=path, status="optional-missing", detail=str(path))
    return DemoAuditItem(label=label, path=path, status="missing", detail=str(path))


def _audit_dir(label: str, path: Path, pattern: str, optional: bool = False) -> DemoAuditItem:
    if path.exists() and path.is_dir():
        matches = sorted(path.glob(pattern))
        if matches:
            return DemoAuditItem(
                label=label,
                path=path,
                status="present",
                detail=f"{path} ({len(matches)} matches)",
            )
        if optional:
            return DemoAuditItem(label=label, path=path, status="optional-missing", detail=f"{path} (0 matches)")
        return DemoAuditItem(label=label, path=path, status="missing", detail=f"{path} (0 matches)")
    if optional:
        return DemoAuditItem(label=label, path=path, status="optional-missing", detail=str(path))
    return DemoAuditItem(label=label, path=path, status="missing", detail=str(path))


def _write_csv_if_missing(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _etl_command(paths: DemoClassPaths, *, include_eliteprospects: bool) -> str:
    command = (
        f"PYTHONPATH=src python3 -m draft_room_intelligence.cli etl-draft-year "
        f"data/processed/demo_{paths.draft_year} "
        f"--draft-year {paths.draft_year} "
        f"--hockeydb-draft-html data/raw/hockeydb/{paths.draft_year}/nhl{paths.draft_year}e.html "
        f"--hockeydb-player-pages-dir data/raw/hockeydb/{paths.draft_year}/player_pages"
    )
    if include_eliteprospects:
        command += f" --eliteprospects-csv data/raw/eliteprospects_{paths.draft_year}.csv"
    label = "Enriched ETL" if include_eliteprospects else "Base ETL"
    return f"{label}: {command}"


def _demo_site_command(paths: DemoClassPaths) -> str:
    return (
        "Build demo site: "
        f"PYTHONPATH=src python3 -m draft_room_intelligence.cli build-demo-site "
        f"data/processed/demo_{paths.draft_year}/final outputs/demo_{paths.draft_year}"
    )
