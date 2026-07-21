"""Plan and execute repeatable ETL across multiple NHL draft classes."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

REQUIRED_FINAL_TABLES = (
    "players.csv",
    "draft_selections.csv",
    "rankings.csv",
    "season_stat_lines.csv",
    "nhl_outcomes.csv",
)
ETL_STATE_FILE = "etl_state.json"
PIPELINE_VERSION = 3
MIN_DRAFT_CLASS_SIZE = 150
MAX_DRAFT_CLASS_SIZE = 300
REQUIRED_COLUMNS = {
    "players.csv": {"player_id", "name", "position", "source"},
    "draft_selections.csv": {
        "player_id",
        "draft_year",
        "team_id",
        "round_number",
        "overall_pick",
        "source",
    },
    "rankings.csv": {"player_id", "draft_year", "source", "rank"},
    "season_stat_lines.csv": {"player_id", "season", "league", "team", "timing"},
    "nhl_outcomes.csv": {"player_id", "nhl_games", "nhl_points"},
}


@dataclass(frozen=True)
class DraftClassETLSpec:
    draft_year: int
    enabled: bool
    base_dir: Path | None
    nhl_draft_json: Path | None
    hockeydb_draft_html: Path | None
    hockeydb_player_pages_dir: Path | None
    eliteprospects_csv: Path | None
    match_map: Path | None
    output_dir: Path
    notes: str = ""


@dataclass(frozen=True)
class DraftClassETLPlan:
    spec: DraftClassETLSpec
    status: str
    base_source: str
    enrichment_status: str
    detail: str


@dataclass(frozen=True)
class DraftClassETLResult:
    draft_year: int
    status: str
    base_source: str
    enrichment_status: str
    output_dir: str
    detail: str
    player_count: int = 0
    selection_count: int = 0
    stat_line_count: int = 0
    quality_status: str = "not_run"


@dataclass(frozen=True)
class NormalizedDatasetAudit:
    passed: bool
    player_count: int
    selection_count: int
    stat_line_count: int
    issues: tuple[str, ...]


@dataclass(frozen=True)
class DraftRangeETLReport:
    results: tuple[DraftClassETLResult, ...]

    @property
    def failed_count(self) -> int:
        return sum(result.status == "failed" for result in self.results)

    @property
    def blocked_count(self) -> int:
        return sum(result.status == "blocked" for result in self.results)

    @property
    def ready_count(self) -> int:
        reusable = {"completed", "skipped_complete", "ready"}
        return sum(result.status in reusable for result in self.results)


DraftYearExecutor = Callable[[DraftClassETLSpec], None]


def load_draft_class_manifest(
    manifest_path: str | Path,
    *,
    project_root: str | Path,
    output_root: str | Path | None = None,
) -> list[DraftClassETLSpec]:
    root = Path(project_root).resolve()
    default_output_root = (
        resolve_path(root, str(output_root))
        if output_root
        else root / "data" / "processed" / "draft_classes"
    )
    with Path(manifest_path).open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    specs: list[DraftClassETLSpec] = []
    seen_years: set[int] = set()
    for row_number, row in enumerate(rows, start=2):
        draft_year = parse_year(row.get("draft_year"), row_number)
        if draft_year in seen_years:
            raise ValueError(f"duplicate draft_year {draft_year} in manifest")
        seen_years.add(draft_year)
        configured_output = optional_path(root, row.get("output_dir"))
        specs.append(
            DraftClassETLSpec(
                draft_year=draft_year,
                enabled=parse_bool(row.get("enabled", "true")),
                base_dir=optional_path(root, row.get("base_dir")),
                nhl_draft_json=optional_path(root, row.get("nhl_draft_json")),
                hockeydb_draft_html=optional_path(root, row.get("hockeydb_draft_html")),
                hockeydb_player_pages_dir=optional_path(root, row.get("hockeydb_player_pages_dir")),
                eliteprospects_csv=optional_path(root, row.get("eliteprospects_csv")),
                match_map=optional_path(root, row.get("match_map")),
                output_dir=configured_output or default_output_root / str(draft_year),
                notes=(row.get("notes") or "").strip(),
            )
        )
    return sorted(specs, key=lambda spec: spec.draft_year)


def filter_draft_class_specs(
    specs: Iterable[DraftClassETLSpec],
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[DraftClassETLSpec]:
    if start_year is not None and end_year is not None and start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")
    return [
        spec
        for spec in specs
        if (start_year is None or spec.draft_year >= start_year)
        and (end_year is None or spec.draft_year <= end_year)
    ]


def plan_draft_class(spec: DraftClassETLSpec, *, force: bool = False) -> DraftClassETLPlan:
    if not spec.enabled:
        return DraftClassETLPlan(
            spec,
            "disabled",
            "none",
            enrichment_status(spec),
            "class disabled in manifest",
        )
    existing_audit = audit_normalized_dataset(spec.output_dir / "final", spec.draft_year)
    state_matches = etl_state_matches(spec)
    if not force and existing_audit.passed and state_matches:
        return DraftClassETLPlan(
            spec,
            "complete",
            resolve_base_source(spec),
            enrichment_status(spec),
            "normalized integrity and input fingerprint match",
        )
    base_source = resolve_base_source(spec)
    if base_source == "missing":
        return DraftClassETLPlan(
            spec,
            "blocked",
            base_source,
            enrichment_status(spec),
            "stage a normalized base, official NHL draft JSON, or HockeyDB draft HTML",
        )
    return DraftClassETLPlan(
        spec,
        "ready",
        base_source,
        enrichment_status(spec),
        (
            "cached inputs changed or ETL state is missing; rebuild required"
            if existing_audit.passed and not state_matches
            else "base ETL can run from cached local inputs"
        ),
    )


def run_draft_range_etl(
    specs: Iterable[DraftClassETLSpec],
    *,
    executor: DraftYearExecutor,
    report_dir: str | Path,
    dry_run: bool = False,
    force: bool = False,
    continue_on_error: bool = True,
) -> DraftRangeETLReport:
    results: list[DraftClassETLResult] = []
    for spec in specs:
        plan = plan_draft_class(spec, force=force)
        if plan.status == "disabled":
            result = result_from_plan(plan, "disabled")
        elif plan.status == "blocked":
            result = result_from_plan(plan, "blocked")
        elif plan.status == "complete":
            result = result_from_plan(plan, "skipped_complete")
        elif dry_run:
            result = result_from_plan(plan, "ready")
        else:
            try:
                executor(spec)
                audit = audit_normalized_dataset(spec.output_dir / "final", spec.draft_year)
                if not audit.passed:
                    raise RuntimeError("normalized integrity failed: " + "; ".join(audit.issues))
                write_etl_state(spec)
                result = result_from_plan(
                    plan,
                    "completed",
                    "ETL completed and required final tables are present",
                    audit=audit,
                )
            # Batch isolation is intentional; each error is recorded by class.
            except Exception as exc:
                result = result_from_plan(plan, "failed", f"{type(exc).__name__}: {exc}")
                results.append(result)
                write_draft_range_report(report_dir, DraftRangeETLReport(tuple(results)))
                if not continue_on_error:
                    raise
                continue
        results.append(result)
        write_draft_range_report(report_dir, DraftRangeETLReport(tuple(results)))
    report = DraftRangeETLReport(tuple(results))
    write_draft_range_report(report_dir, report)
    return report


def write_draft_range_report(
    report_dir: str | Path,
    report: DraftRangeETLReport,
) -> dict[str, Path]:
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "draft_class_runs.csv"
    json_path = root / "draft_class_runs.json"
    summary_path = root / "summary.md"
    fields = [
        "draft_year",
        "status",
        "base_source",
        "enrichment_status",
        "output_dir",
        "detail",
        "player_count",
        "selection_count",
        "stat_line_count",
        "quality_status",
    ]
    rows = [asdict(result) for result in report.results]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    summary_path.write_text(format_draft_range_summary(report), encoding="utf-8")
    return {"csv": csv_path, "json": json_path, "summary": summary_path}


def format_draft_range_summary(report: DraftRangeETLReport) -> str:
    status_counts: dict[str, int] = {}
    for result in report.results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
    lines = [
        "# Draft Class ETL Report",
        "",
        f"- Classes: {len(report.results)}",
        f"- Completed or reusable: {report.ready_count}",
        f"- Failed: {report.failed_count}",
        f"- Blocked: {report.blocked_count}",
        "- Status counts: "
        + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())),
        "",
        "| Year | Status | Players | Stats | Quality | Base | Enrichment | Detail |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for result in report.results:
        lines.append(
            f"| {result.draft_year} | {result.status} | {result.player_count} | "
            f"{result.stat_line_count} | {result.quality_status} | {result.base_source} | "
            f"{result.enrichment_status} | {result.detail} |"
        )
    return "\n".join(lines) + "\n"


def normalized_dataset_complete(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in REQUIRED_FINAL_TABLES)


def etl_state_matches(spec: DraftClassETLSpec) -> bool:
    state_path = spec.output_dir / ETL_STATE_FILE
    if not state_path.is_file():
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return state.get("input_fingerprint") == input_fingerprint(spec)


def write_etl_state(spec: DraftClassETLSpec) -> Path:
    state_path = spec.output_dir / ETL_STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "draft_year": spec.draft_year,
        "pipeline_version": PIPELINE_VERSION,
        "input_fingerprint": input_fingerprint(spec),
        "base_source": resolve_base_source(spec),
        "enrichment_status": enrichment_status(spec),
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


def input_fingerprint(spec: DraftClassETLSpec) -> str:
    inputs: list[tuple[str, str]] = []
    if spec.base_dir and normalized_dataset_complete(spec.base_dir):
        inputs.extend(
            (f"base/{path.relative_to(spec.base_dir)}", file_digest(path))
            for path in sorted(spec.base_dir.rglob("*"))
            if path.is_file()
        )
    elif spec.nhl_draft_json and spec.nhl_draft_json.is_file():
        inputs.append(("nhl_draft_json", file_digest(spec.nhl_draft_json)))
    elif spec.hockeydb_draft_html and spec.hockeydb_draft_html.is_file():
        inputs.append(("hockeydb_draft_html", file_digest(spec.hockeydb_draft_html)))
        if spec.hockeydb_player_pages_dir and spec.hockeydb_player_pages_dir.is_dir():
            inputs.extend(
                (f"hockeydb_player/{path.name}", file_digest(path))
                for path in sorted(spec.hockeydb_player_pages_dir.glob("*.html"))
            )
    if spec.eliteprospects_csv and spec.eliteprospects_csv.is_file():
        inputs.append(("eliteprospects_csv", file_digest(spec.eliteprospects_csv)))
    if spec.match_map and spec.match_map.is_file():
        inputs.append(("match_map", file_digest(spec.match_map)))
    payload = {
        "draft_year": spec.draft_year,
        "enabled": spec.enabled,
        "pipeline_version": PIPELINE_VERSION,
        "inputs": inputs,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_normalized_dataset(path: Path, draft_year: int) -> NormalizedDatasetAudit:
    if not normalized_dataset_complete(path):
        missing = [name for name in REQUIRED_FINAL_TABLES if not (path / name).is_file()]
        return NormalizedDatasetAudit(False, 0, 0, 0, tuple(f"missing {name}" for name in missing))

    issues: list[str] = []
    for filename, required_columns in REQUIRED_COLUMNS.items():
        missing_columns = required_columns - csv_columns(path / filename)
        if missing_columns:
            issues.append(f"{filename} missing columns: {sorted(missing_columns)}")

    players = read_csv(path / "players.csv")
    selections = read_csv(path / "draft_selections.csv")
    rankings = read_csv(path / "rankings.csv")
    outcomes = read_csv(path / "nhl_outcomes.csv")
    stat_lines = read_csv(path / "season_stat_lines.csv")
    player_ids = [row.get("player_id", "") for row in players]
    selection_ids = [row.get("player_id", "") for row in selections]
    if not players:
        issues.append("players table is empty")
    if not MIN_DRAFT_CLASS_SIZE <= len(players) <= MAX_DRAFT_CLASS_SIZE:
        issues.append(
            f"player count {len(players)} outside plausible full-class range "
            f"{MIN_DRAFT_CLASS_SIZE}-{MAX_DRAFT_CLASS_SIZE}"
        )
    if any(
        not row.get("player_id", "").strip()
        or not row.get("name", "").strip()
        or not row.get("position", "").strip()
        or not row.get("source", "").strip()
        for row in players
    ):
        issues.append("players contain blank identity, position, or source fields")
    if len(player_ids) != len(set(player_ids)):
        issues.append("duplicate player_id in players")
    if len(selection_ids) != len(set(selection_ids)):
        issues.append("duplicate player_id in draft selections")
    if set(player_ids) != set(selection_ids):
        issues.append("players and draft selections have different player IDs")
    if any(
        not row.get("team_id", "").strip()
        or not row.get("round_number", "").isdigit()
        or not row.get("source", "").strip()
        for row in selections
    ):
        issues.append("draft selections contain blank team, round, or source fields")
    years = {row.get("draft_year", "") for row in selections}
    if years != {str(draft_year)}:
        issues.append(f"draft selections contain unexpected years: {sorted(years)}")
    picks = [row.get("overall_pick", "") for row in selections]
    if len(picks) != len(set(picks)):
        issues.append("duplicate overall_pick in draft selections")
    if any(not value.isdigit() or int(value) <= 0 for value in picks):
        issues.append("draft selections contain invalid overall_pick values")
    ranking_ids = {row.get("player_id", "") for row in rankings}
    if not set(player_ids).issubset(ranking_ids):
        issues.append("one or more players are missing ranking rows")
    if any(
        not row.get("source", "").strip()
        or not row.get("rank", "").isdigit()
        or int(row["rank"]) <= 0
        for row in rankings
    ):
        issues.append("rankings contain blank source or invalid rank values")
    outcome_ids = [row.get("player_id", "") for row in outcomes]
    if len(outcome_ids) != len(set(outcome_ids)):
        issues.append("duplicate player_id in NHL outcomes")
    if set(outcome_ids) - set(player_ids):
        issues.append("NHL outcomes reference unknown player IDs")
    unknown_stat_ids = {row.get("player_id", "") for row in stat_lines} - set(player_ids)
    if unknown_stat_ids:
        issues.append("season stats reference unknown player IDs")
    return NormalizedDatasetAudit(
        passed=not issues,
        player_count=len(players),
        selection_count=len(selections),
        stat_line_count=len(stat_lines),
        issues=tuple(issues),
    )


def resolve_base_source(spec: DraftClassETLSpec) -> str:
    if spec.base_dir and normalized_dataset_complete(spec.base_dir):
        return "normalized_base"
    if spec.nhl_draft_json and spec.nhl_draft_json.is_file():
        return "nhl_draft_cache"
    if spec.hockeydb_draft_html and spec.hockeydb_draft_html.is_file():
        return "hockeydb_cache"
    return "missing"


def enrichment_status(spec: DraftClassETLSpec) -> str:
    if not spec.eliteprospects_csv:
        return "not_configured"
    if spec.eliteprospects_csv.is_file():
        return "eliteprospects_ready"
    return "eliteprospects_missing"


def result_from_plan(
    plan: DraftClassETLPlan,
    status: str,
    detail: str | None = None,
    audit: NormalizedDatasetAudit | None = None,
) -> DraftClassETLResult:
    resolved_audit = audit
    if resolved_audit is None and status == "skipped_complete":
        resolved_audit = audit_normalized_dataset(
            plan.spec.output_dir / "final",
            plan.spec.draft_year,
        )
    return DraftClassETLResult(
        draft_year=plan.spec.draft_year,
        status=status,
        base_source=plan.base_source,
        enrichment_status=plan.enrichment_status,
        output_dir=str(plan.spec.output_dir),
        detail=detail or plan.detail,
        player_count=resolved_audit.player_count if resolved_audit else 0,
        selection_count=resolved_audit.selection_count if resolved_audit else 0,
        stat_line_count=resolved_audit.stat_line_count if resolved_audit else 0,
        quality_status="pass" if resolved_audit and resolved_audit.passed else "not_run",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def csv_columns(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return set(csv.DictReader(handle).fieldnames or [])


def optional_path(project_root: Path, value: str | None) -> Path | None:
    cleaned = (value or "").strip()
    return resolve_path(project_root, cleaned) if cleaned else None


def resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else project_root / path


def parse_year(value: str | None, row_number: int) -> int:
    try:
        year = int((value or "").strip())
    except ValueError as exc:
        raise ValueError(f"invalid draft_year on manifest row {row_number}") from exc
    if year < 1963 or year > 2100:
        raise ValueError(f"draft_year {year} is outside the supported NHL draft range")
    return year


def parse_bool(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")
