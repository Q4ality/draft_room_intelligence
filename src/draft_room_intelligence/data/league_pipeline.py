"""Operational discovery, collection, enrichment, and audit workflow."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from draft_room_intelligence.data.league_enrichment import (
    LeagueSourceCollectionResult,
    collect_league_sources,
    discover_europe_source_specs,
    expand_chl_history_sources,
    filter_league_sources,
    generate_swehockey_source_specs,
    is_stale_generated_swehockey_source,
    load_league_source_manifest,
    run_league_enrichment_range,
    write_league_source_manifest,
)
from draft_room_intelligence.reports.league_ingestion_audit import (
    write_league_ingestion_audit,
)


@dataclass(frozen=True)
class LeaguePipelineSummary:
    start_year: int
    end_year: int
    discovered_sources: int
    ready_sources: int
    collection_failures: int
    enrichment_failures: int
    audit_issues: int


def run_league_pipeline(
    manifest_path: str | Path,
    class_root: str | Path,
    output_dir: str | Path,
    *,
    project_root: str | Path,
    europe_catalog_path: str | Path,
    start_year: int,
    end_year: int,
    collect: bool = False,
    refresh: bool = False,
    force: bool = False,
    continue_on_error: bool = True,
) -> LeaguePipelineSummary:
    project = Path(project_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    sources = load_league_source_manifest(manifest_path, project_root=project)
    europe_catalog = Path(europe_catalog_path)
    if not europe_catalog.is_absolute():
        europe_catalog = project / europe_catalog
    europe_sources = discover_europe_source_specs(
        europe_catalog,
        project_root=project,
        start_year=start_year,
        end_year=end_year,
    )
    retained = [source for source in sources if source.adapter != "europe"]
    generated_swehockey = generate_swehockey_source_specs(
        cache_root=project / "data/raw/cache/europe_stats",
        start_year=start_year,
        end_year=end_year,
    )
    discovered_ids = {source.source_id for source in generated_swehockey}
    discovered_swehockey_scopes = {
        (source.draft_year, source.league)
        for source in generated_swehockey
    }
    europe_by_source_id = {
        source.source_id: source
        for source in sources
        if source.adapter == "europe"
        and not is_stale_generated_swehockey_source(
            source,
            discovered_ids,
            discovered_swehockey_scopes,
            start_year=start_year,
            end_year=end_year,
        )
    }
    europe_by_source_id.update({source.source_id: source for source in europe_sources})
    sources = retained + list(europe_by_source_id.values())
    sources = expand_chl_history_sources(
        sources,
        start_year=start_year,
        end_year=end_year,
    )
    sources = [
        replace(source, enabled=source.enabled or source.cache_path.is_file())
        for source in sources
        if start_year <= source.draft_year <= end_year
    ]

    collection_results: list[LeagueSourceCollectionResult] = []
    if collect:
        collection_results = collect_league_sources(
            sources,
            refresh=refresh,
            continue_on_error=continue_on_error,
        )
        successful = {
            result.source_id for result in collection_results if result.status != "failed"
        }
        sources = [replace(source, enabled=source.source_id in successful) for source in sources]
    write_collection_results(output / "collection_results.csv", collection_results)

    resolved_manifest = output / "resolved_sources.csv"
    write_league_source_manifest(resolved_manifest, sources, project_root=project)
    ready_sources = filter_league_sources(sources, start_year=start_year, end_year=end_year)
    enrichment = run_league_enrichment_range(
        class_root,
        ready_sources,
        report_dir=output / "enrichment",
        start_year=start_year,
        end_year=end_year,
        force=force,
        continue_on_error=continue_on_error,
    )
    audit = write_league_ingestion_audit(
        class_root,
        output / "audit",
        start_year=start_year,
        end_year=end_year,
    )
    summary = LeaguePipelineSummary(
        start_year=start_year,
        end_year=end_year,
        discovered_sources=len(sources),
        ready_sources=len(ready_sources),
        collection_failures=sum(row.status == "failed" for row in collection_results),
        enrichment_failures=enrichment.failed_count,
        audit_issues=len(audit.issues),
    )
    (output / "run_summary.json").write_text(
        json.dumps(asdict(summary), indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "summary.md").write_text(format_pipeline_summary(summary), encoding="utf-8")
    return summary


def write_collection_results(
    path: Path,
    results: list[LeagueSourceCollectionResult],
) -> None:
    fields = list(LeagueSourceCollectionResult.__dataclass_fields__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)


def format_pipeline_summary(summary: LeaguePipelineSummary) -> str:
    return "\n".join(
        [
            "# League Ingestion Pipeline",
            "",
            f"- Years: {summary.start_year}-{summary.end_year}",
            f"- Discovered sources: {summary.discovered_sources}",
            f"- Ready sources: {summary.ready_sources}",
            f"- Collection failures: {summary.collection_failures}",
            f"- Enrichment failures: {summary.enrichment_failures}",
            f"- Audit issues: {summary.audit_issues}",
            "",
            (
                "Artifacts: `resolved_sources.csv`, `collection_results.csv`, "
                "`enrichment/`, and `audit/`."
            ),
            "",
        ]
    )
