"""Audit systematic source-family ingestion readiness."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.data.nhl_contracts import parse_iso_date, read_source_metadata


SOURCE_FAMILY_COLUMNS = [
    "source_family",
    "priority",
    "draft_years",
    "raw_cache_path",
    "normalized_output_path",
    "doc_path",
    "test_path",
    "owner_stage",
    "notes",
]

AUDIT_COLUMNS = [
    *SOURCE_FAMILY_COLUMNS,
    "raw_cache_status",
    "normalized_status",
    "doc_status",
    "test_status",
    "readiness",
    "next_action",
]


@dataclass(frozen=True)
class SourceFamily:
    source_family: str
    priority: int
    draft_years: str
    raw_cache_path: str
    normalized_output_path: str
    doc_path: str
    test_path: str
    owner_stage: str
    notes: str


@dataclass(frozen=True)
class IngestionAudit:
    source: SourceFamily
    raw_cache_status: str
    normalized_status: str
    doc_status: str
    test_status: str
    readiness: str
    next_action: str

    def to_row(self) -> dict[str, str]:
        return {
            "source_family": self.source.source_family,
            "priority": str(self.source.priority),
            "draft_years": self.source.draft_years,
            "raw_cache_path": self.source.raw_cache_path,
            "normalized_output_path": self.source.normalized_output_path,
            "doc_path": self.source.doc_path,
            "test_path": self.source.test_path,
            "owner_stage": self.source.owner_stage,
            "notes": self.source.notes,
            "raw_cache_status": self.raw_cache_status,
            "normalized_status": self.normalized_status,
            "doc_status": self.doc_status,
            "test_status": self.test_status,
            "readiness": self.readiness,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class IngestionPlanReport:
    manifest_path: Path
    audits: list[IngestionAudit]

    @property
    def ready_count(self) -> int:
        return sum(1 for audit in self.audits if audit.readiness == "ready")

    @property
    def blocked_count(self) -> int:
        return sum(1 for audit in self.audits if audit.readiness == "blocked")


def write_ingestion_plan_report(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    project_root: str | Path = ".",
) -> IngestionPlanReport:
    report = build_ingestion_plan_report(manifest_path, project_root=project_root)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = [audit.to_row() for audit in report.audits]
    write_csv(root / "source_family_audit.csv", AUDIT_COLUMNS, rows)
    (root / "summary.md").write_text(format_ingestion_plan_report(report), encoding="utf-8")
    return report


def build_ingestion_plan_report(
    manifest_path: str | Path,
    *,
    project_root: str | Path = ".",
) -> IngestionPlanReport:
    manifest = Path(manifest_path)
    root = Path(project_root)
    families = load_source_families(manifest)
    audits = [audit_source_family(family, root) for family in families]
    return IngestionPlanReport(manifest_path=manifest, audits=audits)


def load_source_families(path: Path) -> list[SourceFamily]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    families = [
        SourceFamily(
            source_family=row.get("source_family", ""),
            priority=int_value(row.get("priority")),
            draft_years=row.get("draft_years", ""),
            raw_cache_path=row.get("raw_cache_path", ""),
            normalized_output_path=row.get("normalized_output_path", ""),
            doc_path=row.get("doc_path", ""),
            test_path=row.get("test_path", ""),
            owner_stage=row.get("owner_stage", ""),
            notes=row.get("notes", ""),
        )
        for row in rows
        if row.get("source_family")
    ]
    return sorted(families, key=lambda family: (family.priority, family.source_family))


def audit_source_family(family: SourceFamily, project_root: Path) -> IngestionAudit:
    raw_path = project_root / family.raw_cache_path
    raw_status = (
        source_access_cache_status(raw_path)
        if family.owner_stage == "source_access"
        else path_status(raw_path)
    )
    normalized_status = path_status(project_root / family.normalized_output_path)
    doc_status = path_status(project_root / family.doc_path)
    test_status = path_status(project_root / family.test_path)
    readiness = (
        "blocked"
        if family.owner_stage == "source_access" and raw_status == "missing"
        else classify_readiness(raw_status, normalized_status, doc_status, test_status)
    )
    return IngestionAudit(
        source=family,
        raw_cache_status=raw_status,
        normalized_status=normalized_status,
        doc_status=doc_status,
        test_status=test_status,
        readiness=readiness,
        next_action=next_action(family, raw_status, normalized_status, doc_status, test_status),
    )


def classify_readiness(raw_status: str, normalized_status: str, doc_status: str, test_status: str) -> str:
    if (
        raw_status == "present"
        and normalized_status == "present"
        and doc_status == "present"
        and test_status == "present"
    ):
        return "ready"
    if raw_status == "missing" and normalized_status == "missing":
        return "blocked"
    return "partial"


def next_action(
    family: SourceFamily,
    raw_status: str,
    normalized_status: str,
    doc_status: str,
    test_status: str,
) -> str:
    if family.owner_stage == "source_access" and raw_status == "missing":
        return "Obtain a permitted dated export or API credential; do not substitute current web tables."
    if raw_status == "missing" and normalized_status == "missing":
        return "Collect or stage cached source files before adapter work."
    if raw_status == "missing":
        return "Stage cached raw inputs so this source can rerun without curated/manual files."
    if normalized_status == "missing":
        return "Parse cached source files into normalized source tables."
    if test_status == "missing":
        return "Add parser or report tests for this source family."
    if doc_status == "missing":
        return "Document source contract, known gaps, and rerun command."
    if family.owner_stage in {"adapter", "scale_to_full_2026"}:
        return "Replace curated/sample inputs with a repeatable cache-first adapter."
    if family.owner_stage == "refine_snapshot":
        return "Refine snapshot semantics and NHL/AHL readiness separation."
    return "Run merge, coverage audit, and demo sanity comparison."


def format_ingestion_plan_report(report: IngestionPlanReport) -> str:
    lines = [
        "# Systematic Ingestion Plan Audit",
        "",
        f"- Manifest: `{report.manifest_path}`",
        f"- Source families: {len(report.audits)}",
        f"- Ready: {report.ready_count}",
        f"- Blocked: {report.blocked_count}",
        "",
        "## Source-Family Status",
        "",
        "| Priority | Source family | Stage | Raw | Normalized | Tests | Readiness | Next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for audit in report.audits:
        row = audit.to_row()
        lines.append(
            "| {priority} | {source_family} | {owner_stage} | {raw_cache_status} | "
            "{normalized_status} | {test_status} | {readiness} | {next_action} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Operating Rule",
            "",
            "Do not add another one-off enrichment pack unless it also updates this manifest, has a cached input path, and produces an auditable normalized output or explicit blocker.",
        ]
    )
    return "\n".join(lines) + "\n"


def path_status(path: Path) -> str:
    if not str(path):
        return "missing"
    return "present" if path.exists() else "missing"


def source_access_cache_status(path: Path) -> str:
    if not path.is_dir():
        return "missing"
    try:
        expected_snapshot = parse_iso_date(path.name)
    except ValueError:
        return "missing"
    for csv_path in path.glob("*.csv"):
        metadata_path = csv_path.with_suffix(".metadata.json")
        if not metadata_path.is_file():
            continue
        try:
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                first_row = next(reader, [])
            if not header or not any(value.strip() for value in first_row):
                continue
            read_source_metadata(
                metadata_path,
                input_csv=csv_path,
                expected_snapshot=expected_snapshot,
            )
        except (OSError, ValueError):
            continue
        return "present"
    return "missing"


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
