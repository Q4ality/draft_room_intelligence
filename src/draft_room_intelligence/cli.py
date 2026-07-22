"""Command-line entry point for the PoC."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import unicodedata
from dataclasses import replace
from datetime import date
from pathlib import Path

from draft_room_intelligence.data.ahl_api import (
    DEFAULT_AHL_SEASON_ID,
    DEFAULT_AHL_SEASON_LABEL,
    import_ahl_rosters,
)
from draft_room_intelligence.data.chl_stats import ChlStatSource, enrich_chl_stats
from draft_room_intelligence.data.demo_data import (
    audit_demo_class,
    format_demo_audit_report,
    scaffold_demo_class,
)
from draft_room_intelligence.data.draft_range_etl import (
    DraftClassETLSpec,
    filter_draft_class_specs,
    load_draft_class_manifest,
)
from draft_room_intelligence.data.draft_range_etl import (
    run_draft_range_etl as execute_draft_range_etl,
)
from draft_room_intelligence.data.eliteprospects_csv import (
    format_eliteprospects_validation_report,
    validate_eliteprospects_export,
    write_eliteprospects_normalized_tables,
)
from draft_room_intelligence.data.eliteprospects_pdf import (
    DEFAULT_VISION_MODEL,
    write_eliteprospects_pdf_tables,
)
from draft_room_intelligence.data.ep_pdf_overlay import (
    overlay_ep_pdf_demo_dataset,
    write_overlay_report,
)
from draft_room_intelligence.data.etl_config import DraftYearETLConfig
from draft_room_intelligence.data.historical_csv import load_historical_prospects_csv
from draft_room_intelligence.data.hockeydb_base import (
    HockeyDbBaseETLConfig,
    generate_hockeydb_base_tables,
)
from draft_room_intelligence.data.league_enrichment import (
    SUPPORTED_ADAPTERS,
    collect_league_sources,
    collect_ushl_season_catalog,
    discover_chl_source_specs,
    discover_europe_source_specs,
    discover_ncaa_source_specs,
    discover_ushl_source_specs,
    filter_league_sources,
    load_league_source_manifest,
    merge_league_source_specs,
    run_league_enrichment_range,
    write_league_source_manifest,
)
from draft_room_intelligence.data.league_pipeline import run_league_pipeline
from draft_room_intelligence.data.merge_quality import (
    build_merge_quality_report,
    format_merge_quality_report,
)
from draft_room_intelligence.data.nhl_api import import_nhl_rosters
from draft_room_intelligence.data.nhl_contracts import (
    enrich_roster_contracts,
    normalize_contract_export,
)
from draft_room_intelligence.data.nhl_draft import (
    collect_nhl_draft_range,
    generate_nhl_draft_base_tables,
)
from draft_room_intelligence.data.normalized_merge import (
    generate_match_map_template,
    merge_normalized_source_tables,
)
from draft_room_intelligence.data.normalized_tables import load_normalized_historical_prospects
from draft_room_intelligence.data.open_stats_csv import OpenStatsCsvSource, enrich_open_stats_csv
from draft_room_intelligence.data.puckpedia_stats import enrich_puckpedia_stats
from draft_room_intelligence.data.roster_assignments import (
    enrich_cross_organization_assignment_dates,
)
from draft_room_intelligence.data.roster_snapshots import (
    build_point_in_time_roster,
    normalize_roster_snapshot,
)
from draft_room_intelligence.data.team_rosters import (
    build_depth_rows,
    format_depth_markdown,
    load_roster_csv,
    write_depth_csv,
    write_roster_csv,
)
from draft_room_intelligence.data.ushl_stats import UShlStatSource, enrich_ushl_stats
from draft_room_intelligence.data.wikipedia_bio import enrich_wikipedia_bios
from draft_room_intelligence.data.wikipedia_career_stats import enrich_wikipedia_career_stats
from draft_room_intelligence.evaluation.baselines import (
    adjusted_production_scores,
    consensus_scores,
    contextual_scores,
    evaluate_historical_scores,
    projection_scores,
    role_aware_scores,
    role_specific_hybrid_scores,
    weighted_hybrid_scores,
)
from draft_room_intelligence.modeling.feature_table import (
    build_feature_rows,
    load_advanced_stat_summaries,
    write_feature_table,
)
from draft_room_intelligence.modeling.role_models import (
    evaluate_role_specific_models,
    write_model_summary,
)
from draft_room_intelligence.optimization.board import rank_board
from draft_room_intelligence.projection.baseline import project_board
from draft_room_intelligence.reports.codex_context_routes import write_codex_context_routes_report
from draft_room_intelligence.reports.codex_routing_audit import write_codex_routing_audit
from draft_room_intelligence.reports.codex_task_routing import write_codex_task_routing_report
from draft_room_intelligence.reports.codex_usage import write_codex_usage_report
from draft_room_intelligence.reports.demo_acceptance import write_demo_acceptance_report
from draft_room_intelligence.reports.demo_brief import write_demo_meeting_brief
from draft_room_intelligence.reports.demo_export import (
    build_demo_export_bundle,
    export_demo_package,
)
from draft_room_intelligence.reports.demo_gaps import write_demo_gap_report
from draft_room_intelligence.reports.demo_modeling import write_demo_modeling_report
from draft_room_intelligence.reports.demo_sanity import write_demo_sanity_report
from draft_room_intelligence.reports.demo_site import write_demo_site
from draft_room_intelligence.reports.historical_validation import write_historical_validation_report
from draft_room_intelligence.reports.ingestion_plan import write_ingestion_plan_report
from draft_room_intelligence.reports.league_ingestion_audit import write_league_ingestion_audit
from draft_room_intelligence.reports.player_card import render_player_card
from draft_room_intelligence.reports.prospect_stat_audit import write_prospect_stat_audit
from draft_room_intelligence.reports.russian_coverage import write_russian_coverage_report
from draft_room_intelligence.reports.team_system_audit import write_team_system_audit
from draft_room_intelligence.sample_data import sample_prospects, sample_team_context
from draft_room_intelligence.scouting.extraction import extract_scouting_features


def main() -> None:
    load_env_file(Path(".env"))
    parser = argparse.ArgumentParser(prog="draft-room-intel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo", help="Run the sample projection + team-fit pipeline.")
    scaffold_demo_parser = subparsers.add_parser(
        "scaffold-demo-class",
        help="Create the local folder and template structure for a demo draft class.",
    )
    scaffold_demo_parser.add_argument(
        "--draft-year", type=int, required=True, help="NHL draft year."
    )
    audit_demo_parser = subparsers.add_parser(
        "audit-demo-class",
        help="Audit whether a demo draft class has the expected local source files.",
    )
    audit_demo_parser.add_argument("--draft-year", type=int, required=True, help="NHL draft year.")
    import_ep_parser = subparsers.add_parser(
        "import-eliteprospects",
        help="Convert a local Elite Prospects CSV export into normalized project tables.",
    )
    import_ep_parser.add_argument("export_path", type=Path, help="Path to the source CSV export.")
    import_ep_parser.add_argument(
        "output_dir", type=Path, help="Directory for normalized CSV output."
    )
    import_ep_parser.add_argument("--draft-year", type=int, required=True, help="NHL draft year.")
    import_ep_parser.add_argument(
        "--timing",
        default="pre_draft",
        choices=("pre_draft", "post_draft"),
        help="Default timing for stat rows without a timing column.",
    )
    import_ep_pdf_parser = subparsers.add_parser(
        "import-eliteprospects-pdf",
        help="Convert a local Elite Prospects draft-guide PDF into normalized project tables.",
    )
    import_ep_pdf_parser.add_argument("pdf_path", type=Path, help="Path to the source PDF guide.")
    import_ep_pdf_parser.add_argument(
        "output_dir", type=Path, help="Directory for normalized CSV output."
    )
    import_ep_pdf_parser.add_argument(
        "--draft-year", type=int, required=True, help="NHL draft year."
    )
    import_ep_pdf_parser.add_argument(
        "--page-start",
        type=int,
        default=1,
        help="First 1-based PDF page to scan.",
    )
    import_ep_pdf_parser.add_argument(
        "--page-end",
        type=int,
        help="Last 1-based PDF page to scan. Defaults to the full document.",
    )
    import_ep_pdf_parser.add_argument(
        "--profile-limit",
        type=int,
        help="Optional number of parsed player profiles to stop after.",
    )
    import_ep_pdf_parser.add_argument(
        "--index-page-start",
        type=int,
        help="First 1-based PDF page to scan for the player index. Defaults to 5 when profile scan starts later.",
    )
    import_ep_pdf_parser.add_argument(
        "--index-page-end",
        type=int,
        help="Last 1-based PDF page to scan for the player index. Defaults to the page before --page-start.",
    )
    import_ep_pdf_parser.add_argument(
        "--vision-missing-tool-grades",
        action="store_true",
        help="Use OpenAI vision to fill missing PDF tool-grade values from rendered profile pages.",
    )
    import_ep_pdf_parser.add_argument(
        "--vision-model",
        default=None,
        help="OpenAI vision model for missing tool-grade extraction.",
    )
    import_ep_pdf_parser.add_argument(
        "--pdftoppm-path",
        default=os.environ.get("PDFTOPPM_PATH", "pdftoppm"),
        help="Path to Poppler pdftoppm used for rendering vision pages.",
    )
    import_ep_pdf_parser.add_argument(
        "--vision-render-dpi",
        type=int,
        default=160,
        help="DPI for rendered PDF page images sent to the vision model.",
    )
    import_ep_pdf_parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional env file with OPENAI_API_KEY and related settings.",
    )
    overlay_ep_pdf_parser = subparsers.add_parser(
        "overlay-eliteprospects-pdf-demo",
        help="Overlay normalized Elite Prospects PDF guide tables onto a demo final dataset.",
    )
    overlay_ep_pdf_parser.add_argument(
        "base_dir", type=Path, help="Existing demo final dataset directory."
    )
    overlay_ep_pdf_parser.add_argument(
        "ep_pdf_dir", type=Path, help="Directory created by import-eliteprospects-pdf."
    )
    overlay_ep_pdf_parser.add_argument(
        "output_dir", type=Path, help="Output directory for the enriched final dataset."
    )
    overlay_ep_pdf_parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.9,
        help="Minimum normalized-name similarity for fuzzy EP PDF matches.",
    )
    validate_ep_parser = subparsers.add_parser(
        "validate-eliteprospects",
        help="Validate a local Elite Prospects CSV export before import.",
    )
    validate_ep_parser.add_argument("export_path", type=Path, help="Path to the source CSV export.")
    merge_ep_parser = subparsers.add_parser(
        "merge-eliteprospects",
        help="Overlay normalized Elite Prospects tables onto a base draft-year dataset.",
    )
    merge_ep_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    merge_ep_parser.add_argument(
        "eliteprospects_dir",
        type=Path,
        help="Directory created by import-eliteprospects.",
    )
    merge_ep_parser.add_argument("output_dir", type=Path, help="Directory for merged output.")
    merge_ep_parser.add_argument(
        "--replace-timing",
        default="pre_draft",
        help="Base stat-line timing to replace for matched players. Use '' to append only.",
    )
    merge_ep_parser.add_argument(
        "--match-map",
        type=Path,
        help="Optional CSV with source_player_id,base_player_id manual matches.",
    )
    quality_parser = subparsers.add_parser(
        "report-merge-quality",
        help="Print a quality report for a source-overlaid normalized dataset.",
    )
    quality_parser.add_argument(
        "base_dir", type=Path, help="Original normalized dataset directory."
    )
    quality_parser.add_argument(
        "source_dir", type=Path, help="Normalized source dataset directory."
    )
    quality_parser.add_argument(
        "merged_dir", type=Path, help="Merged normalized dataset directory."
    )
    quality_parser.add_argument(
        "--source-name", default="eliteprospects", help="Source label to audit."
    )
    quality_parser.add_argument("--timing", default="pre_draft", help="Stat-line timing to audit.")
    template_parser = subparsers.add_parser(
        "generate-match-map-template",
        help="Create a reviewed match-map starter CSV from unmatched source players.",
    )
    template_parser.add_argument("base_dir", type=Path, help="Base normalized dataset directory.")
    template_parser.add_argument(
        "unmatched_source_players",
        type=Path,
        help="Path to unmatched_source_players.csv from a merge output.",
    )
    template_parser.add_argument("output_path", type=Path, help="Path for the template CSV.")
    template_parser.add_argument(
        "--candidate-count",
        type=int,
        default=3,
        help="Number of closest base-player candidates to include.",
    )
    process_ep_parser = subparsers.add_parser(
        "process-eliteprospects",
        help="Run Elite Prospects import, merge, quality report, and match-template generation.",
    )
    process_ep_parser.add_argument("export_path", type=Path, help="Path to the source CSV export.")
    process_ep_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    process_ep_parser.add_argument(
        "source_output_dir", type=Path, help="Directory for imported EP tables."
    )
    process_ep_parser.add_argument(
        "merged_output_dir", type=Path, help="Directory for merged output."
    )
    process_ep_parser.add_argument("--draft-year", type=int, required=True, help="NHL draft year.")
    process_ep_parser.add_argument(
        "--timing",
        default="pre_draft",
        choices=("pre_draft", "post_draft"),
        help="Default timing for imported stat rows.",
    )
    process_ep_parser.add_argument(
        "--replace-timing",
        default="pre_draft",
        help="Base stat-line timing to replace for matched players. Use '' to append only.",
    )
    process_ep_parser.add_argument(
        "--match-map",
        type=Path,
        help="Optional reviewed match map CSV.",
    )
    process_ep_parser.add_argument(
        "--match-template-output",
        type=Path,
        help="Path for generated match-map template. Defaults inside merged output dir.",
    )
    process_ep_parser.add_argument(
        "--candidate-count",
        type=int,
        default=3,
        help="Number of closest base-player candidates to include in the template.",
    )
    wiki_bio_parser = subparsers.add_parser(
        "enrich-wikipedia-bio",
        help="Enrich normalized player bio fields from public Wikipedia player pages.",
    )
    wiki_bio_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    wiki_bio_parser.add_argument(
        "output_dir", type=Path, help="Directory for enriched normalized output."
    )
    wiki_bio_parser.add_argument(
        "--limit",
        type=int,
        help="Optional number of players to scan, useful for web smoke tests.",
    )
    wiki_bio_parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.2,
        help="Delay between Wikipedia player lookups to avoid rate limiting.",
    )
    wiki_bio_parser.add_argument(
        "--enable-search-fallback",
        action="store_true",
        help="Try Wikipedia search for names without exact-title pages. Slower and more API-heavy.",
    )
    wiki_bio_parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress after this many scanned players. Use 0 to disable.",
    )
    wiki_bio_parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Optional local cache directory for Wikipedia lookup results.",
    )
    chl_stats_parser = subparsers.add_parser(
        "enrich-chl-stats",
        help="Overlay public CHL skater stat pages onto a normalized draft-year dataset.",
    )
    chl_stats_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    chl_stats_parser.add_argument(
        "output_dir", type=Path, help="Directory for CHL-enriched output."
    )
    chl_stats_parser.add_argument(
        "--source",
        action="append",
        required=True,
        help=(
            "CHL stat source as league,season,url[,local_html_path][,regular|playoffs]. "
            "Example: OHL,2024-25,https://chl.ca/ohl/stats/players/79/all/points/all,,regular"
        ),
    )
    ushl_stats_parser = subparsers.add_parser(
        "enrich-ushl-stats",
        help="Overlay official USHL HockeyTech skater feeds onto a normalized draft-year dataset.",
    )
    ushl_stats_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    ushl_stats_parser.add_argument(
        "output_dir", type=Path, help="Directory for USHL-enriched output."
    )
    ushl_stats_parser.add_argument(
        "--source",
        action="append",
        required=True,
        help=(
            "USHL feed source as season,season_id,regular|playoffs[,local_json_path]. "
            "Example: 2024-25,85,regular"
        ),
    )
    open_stats_parser = subparsers.add_parser(
        "enrich-open-stats-csv",
        help="Overlay flexible open-source stat CSVs onto a normalized draft-year dataset.",
    )
    open_stats_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    open_stats_parser.add_argument("output_dir", type=Path, help="Directory for enriched output.")
    open_stats_parser.add_argument(
        "--source",
        action="append",
        required=True,
        help=(
            "Open stat CSV source as csv_path,source_label,season[,league][,regular|playoffs]. "
            "Example: ncaa.csv,collegehockeyinc,2024-25,NCAA,regular"
        ),
    )
    open_stats_parser.add_argument(
        "--allow-new-leagues",
        action="store_true",
        help="Allow curated CSV rows to append by exact normalized player name even if the league is not already present.",
    )
    wiki_career_stats_parser = subparsers.add_parser(
        "enrich-wikipedia-career-stats",
        help="Overlay Wikipedia career-stat tables onto a normalized draft-year dataset.",
    )
    wiki_career_stats_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    wiki_career_stats_parser.add_argument(
        "output_dir", type=Path, help="Directory for enriched output."
    )
    wiki_career_stats_parser.add_argument(
        "--season", required=True, help="Season to extract, e.g. 2024-25."
    )
    wiki_career_stats_parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Optional cache directory for fetched Wikipedia wikitext pages.",
    )
    wiki_career_stats_parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.5,
        help="Delay between Wikipedia page lookups to reduce rate-limit risk.",
    )
    puckpedia_stats_parser = subparsers.add_parser(
        "enrich-puckpedia-stats",
        help="Add same-season public stat rows from PuckPedia player pages.",
    )
    puckpedia_stats_parser.add_argument(
        "base_dir", type=Path, help="Existing normalized dataset directory."
    )
    puckpedia_stats_parser.add_argument(
        "output_dir", type=Path, help="Directory for enriched output."
    )
    puckpedia_stats_parser.add_argument(
        "--season", required=True, help="Season to extract, e.g. 2024-25."
    )
    puckpedia_stats_parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Optional cache directory for fetched PuckPedia HTML pages.",
    )
    puckpedia_stats_parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.5,
        help="Delay between PuckPedia page requests.",
    )
    puckpedia_stats_parser.add_argument(
        "--limit",
        type=int,
        help="Optional player limit for smoke tests.",
    )
    feature_table_parser = subparsers.add_parser(
        "export-feature-table",
        help="Build and export a reusable player-year feature table from historical prospect data.",
    )
    feature_table_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    feature_table_parser.add_argument(
        "output_path", type=Path, help="CSV path for exported features."
    )
    role_models_parser = subparsers.add_parser(
        "evaluate-role-models",
        help="Fit simple role-specific models on the feature table and print evaluation metrics.",
    )
    role_models_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    role_models_parser.add_argument(
        "--feature-output",
        type=Path,
        help="Optional CSV path for exported feature rows.",
    )
    role_models_parser.add_argument(
        "--model-output",
        type=Path,
        help="Optional CSV path for fitted role-model coefficients.",
    )
    role_models_parser.add_argument(
        "--precision-n",
        type=int,
        default=25,
        help="Number of top-ranked players to use for precision@N.",
    )
    validation_parser = subparsers.add_parser(
        "report-historical-validation",
        help="Compare draft-board scoring approaches against historical NHL outcomes.",
    )
    validation_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    validation_parser.add_argument(
        "output_dir", type=Path, help="Directory for validation report artifacts."
    )
    validation_parser.add_argument(
        "--precision-n",
        type=int,
        default=25,
        help="Number of top-ranked players to use for precision@N.",
    )
    validation_parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of top-ranked players to use for board lift metrics.",
    )
    team_depth_parser = subparsers.add_parser(
        "report-team-depth",
        help="Build NHL/AHL organizational role-depth report from normalized roster CSV.",
    )
    team_depth_parser.add_argument("roster_csv", type=Path, help="Normalized roster CSV path.")
    team_depth_parser.add_argument(
        "output_dir", type=Path, help="Directory for depth report artifacts."
    )
    team_system_audit_parser = subparsers.add_parser(
        "audit-team-systems",
        help="Audit all NHL organizations for roster-fit and pipeline interpretation artifacts.",
    )
    team_system_audit_parser.add_argument(
        "roster_csv", type=Path, help="Merged normalized NHL/AHL roster CSV path."
    )
    team_system_audit_parser.add_argument(
        "demo_output_dir", type=Path, help="Demo output directory with players.json."
    )
    team_system_audit_parser.add_argument(
        "output_dir", type=Path, help="Directory for audit report artifacts."
    )
    prospect_stat_audit_parser = subparsers.add_parser(
        "audit-prospect-stats",
        help="Build draft prospect skater/goalie stat summaries from normalized dataset directories.",
    )
    prospect_stat_audit_parser.add_argument(
        "output_dir", type=Path, help="Directory for prospect stat audit artifacts."
    )
    prospect_stat_audit_parser.add_argument(
        "dataset_dirs",
        nargs="+",
        type=Path,
        help="One or more normalized source directories with players/rankings/season_stat_lines CSVs.",
    )
    prospect_stat_audit_parser.add_argument(
        "--draft-year", type=int, help="Draft year label for source rows without one."
    )
    ingestion_plan_parser = subparsers.add_parser(
        "report-ingestion-plan",
        help="Audit systematic source-family ingestion readiness from a manifest CSV.",
    )
    ingestion_plan_parser.add_argument(
        "manifest_csv",
        type=Path,
        help="Source-family manifest CSV, usually data/reference/ingestion_source_families.csv.",
    )
    ingestion_plan_parser.add_argument(
        "output_dir", type=Path, help="Directory for ingestion audit artifacts."
    )
    ingestion_plan_parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root used to resolve manifest paths.",
    )
    league_audit_parser = subparsers.add_parser(
        "audit-league-ingestion",
        help="Audit normalized league coverage, conflicts, duplicates, and advanced samples.",
    )
    league_audit_parser.add_argument("class_root", type=Path)
    league_audit_parser.add_argument("output_dir", type=Path)
    league_audit_parser.add_argument("--start-year", type=int, required=True)
    league_audit_parser.add_argument("--end-year", type=int, required=True)
    russian_audit_parser = subparsers.add_parser(
        "audit-russian-coverage",
        help="Audit KHL, VHL, and MHL evidence and produce the next player review queue.",
    )
    russian_audit_parser.add_argument("dataset_dir", type=Path)
    russian_audit_parser.add_argument("output_dir", type=Path)
    russian_audit_parser.add_argument("--draft-year", type=int, required=True)
    codex_usage_parser = subparsers.add_parser(
        "report-codex-usage",
        help="Build routing usage benchmark summary and dashboard from a run-log CSV.",
    )
    codex_usage_parser.add_argument(
        "run_log_csv", type=Path, help="CSV with baseline/routed benchmark run rows."
    )
    codex_usage_parser.add_argument(
        "output_dir", type=Path, help="Directory for usage report artifacts."
    )
    codex_routing_parser = subparsers.add_parser(
        "audit-codex-routing",
        help="Audit project Codex routing config, custom agents, and repo skill discovery links.",
    )
    codex_routing_parser.add_argument(
        "output_dir", type=Path, help="Directory for routing audit artifacts."
    )
    codex_routing_parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root containing AGENTS.md, .codex, .agents, and skills.",
    )
    codex_context_parser = subparsers.add_parser(
        "report-codex-context-routes",
        help="Audit bounded context routes used to reduce repeated broad repo exploration.",
    )
    codex_context_parser.add_argument(
        "manifest_csv",
        type=Path,
        help="Context route manifest CSV, usually data/reference/codex_context_routes.csv.",
    )
    codex_context_parser.add_argument(
        "output_dir", type=Path, help="Directory for context route artifacts."
    )
    codex_context_parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root used to resolve route paths.",
    )
    codex_task_routing_parser = subparsers.add_parser(
        "report-codex-task-routing",
        help="Audit task-level Codex routing rules for context route, agent, and reasoning selection.",
    )
    codex_task_routing_parser.add_argument(
        "manifest_csv",
        type=Path,
        help="Task routing manifest CSV, usually data/reference/codex_task_routing.csv.",
    )
    codex_task_routing_parser.add_argument(
        "context_routes_csv",
        type=Path,
        help="Context route manifest CSV, usually data/reference/codex_context_routes.csv.",
    )
    codex_task_routing_parser.add_argument(
        "output_dir", type=Path, help="Directory for task routing artifacts."
    )
    proxy_roster_parser = subparsers.add_parser(
        "create-preseason-roster-proxy",
        help="Create a draft-night-safe roster proxy by removing draft-class players from a current roster CSV.",
    )
    proxy_roster_parser.add_argument(
        "roster_csv", type=Path, help="Current normalized roster CSV path."
    )
    proxy_roster_parser.add_argument(
        "data_path", type=Path, help="Normalized draft-class dataset directory."
    )
    proxy_roster_parser.add_argument(
        "output_csv", type=Path, help="Filtered proxy roster CSV output path."
    )
    proxy_roster_parser.add_argument(
        "--audit-csv",
        type=Path,
        help="Optional audit CSV for removed roster rows.",
    )
    merge_rosters_parser = subparsers.add_parser(
        "merge-roster-csvs",
        help="Merge normalized roster CSV files into one roster-depth input.",
    )
    merge_rosters_parser.add_argument(
        "output_csv", type=Path, help="Merged normalized roster CSV output path."
    )
    merge_rosters_parser.add_argument(
        "input_csvs", nargs="+", type=Path, help="Input normalized roster CSV paths."
    )
    merge_rosters_parser.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Keep same-organization same-player NHL/AHL duplicate rows instead of selecting the best assignment proxy.",
    )
    merge_rosters_parser.add_argument(
        "--resolve-cross-org-assignments",
        action="store_true",
        help="Resolve traded NHL/AHL players by their latest official game date.",
    )
    merge_rosters_parser.add_argument(
        "--nhl-season",
        default="20242025",
        help="NHL season used for cross-organization game-log resolution.",
    )
    merge_rosters_parser.add_argument(
        "--assignment-cache-dir",
        type=Path,
        help="Optional cache directory for NHL and AHL assignment game logs.",
    )
    normalize_snapshot_parser = subparsers.add_parser(
        "normalize-roster-snapshot",
        help="Normalize a permitted full-league point-in-time NHL rights export.",
    )
    normalize_snapshot_parser.add_argument("input_csv", type=Path, help="Cached source export CSV.")
    normalize_snapshot_parser.add_argument("output_csv", type=Path, help="Normalized snapshot CSV.")
    normalize_snapshot_parser.add_argument(
        "--snapshot-date", required=True, help="Historical cutoff in YYYY-MM-DD format."
    )
    normalize_snapshot_parser.add_argument(
        "--metadata-json", required=True, type=Path, help="Source metadata sidecar."
    )
    normalize_snapshot_parser.add_argument(
        "--audit-csv", type=Path, help="Optional row-level normalization audit."
    )
    build_snapshot_parser = subparsers.add_parser(
        "build-point-in-time-roster",
        help="Apply a normalized rights snapshot to historical NHL/AHL season-stat rows.",
    )
    build_snapshot_parser.add_argument(
        "base_roster_csv", type=Path, help="Historical season-stat roster CSV."
    )
    build_snapshot_parser.add_argument(
        "snapshot_csv", type=Path, help="Normalized point-in-time rights snapshot CSV."
    )
    build_snapshot_parser.add_argument(
        "output_csv", type=Path, help="Point-in-time roster output CSV."
    )
    build_snapshot_parser.add_argument(
        "--snapshot-date",
        required=True,
        help="Expected historical cutoff in YYYY-MM-DD format.",
    )
    build_snapshot_parser.add_argument(
        "--audit-csv", type=Path, help="Optional match and exclusion audit CSV."
    )
    ahl_rosters_parser = subparsers.add_parser(
        "import-ahl-rosters",
        help="Import official AHL historical stats and roster details into normalized roster CSV.",
    )
    ahl_rosters_parser.add_argument(
        "output_csv", type=Path, help="Path for normalized AHL roster CSV output."
    )
    ahl_rosters_parser.add_argument(
        "--season-id",
        default=DEFAULT_AHL_SEASON_ID,
        help="AHL HockeyTech season id. Defaults to 86, the 2024-25 regular season.",
    )
    ahl_rosters_parser.add_argument(
        "--season-label",
        default=DEFAULT_AHL_SEASON_LABEL,
        help="Human-readable source season label for logs.",
    )
    ahl_rosters_parser.add_argument(
        "--minimum-games",
        type=int,
        default=1,
        help="Minimum AHL games played required for inclusion.",
    )
    ahl_rosters_parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=date(2025, 6, 1),
        help="Date used for player age and snapshot provenance, in YYYY-MM-DD format.",
    )
    nhl_rosters_parser = subparsers.add_parser(
        "import-nhl-rosters",
        help="Import current or historical-season NHL rosters and club stats into normalized roster CSV.",
    )
    nhl_rosters_parser.add_argument(
        "output_csv", type=Path, help="Path for normalized roster CSV output."
    )
    nhl_rosters_parser.add_argument(
        "--teams",
        nargs="+",
        help="NHL team abbreviations to import. Defaults to all known NHL teams.",
    )
    nhl_rosters_parser.add_argument(
        "--season",
        default="",
        help=(
            "Optional NHL season id for both roster and club stats, for example 20242025. "
            "Without it, the current roster endpoint is used."
        ),
    )
    nhl_rosters_parser.add_argument(
        "--game-type",
        type=int,
        default=2,
        help="NHL game type for club stats. 2 is regular season, 3 is playoffs.",
    )
    nhl_rosters_parser.add_argument(
        "--roster-json-dir",
        type=Path,
        help="Optional cached roster JSON directory with files like NYI.roster.json.",
    )
    nhl_rosters_parser.add_argument(
        "--stats-json-dir",
        type=Path,
        help="Optional cached club-stats JSON directory with files like NYI.stats.json.",
    )
    nhl_rosters_parser.add_argument(
        "--cache-json-dir",
        type=Path,
        help="Optional directory where fetched roster and club-stat JSON payloads are cached.",
    )
    contract_parser = subparsers.add_parser(
        "enrich-roster-contracts",
        help="Overlay cached NHL contract and cap evidence onto a normalized roster CSV.",
    )
    contract_parser.add_argument("roster_csv", type=Path, help="Normalized NHL/AHL roster CSV.")
    contract_parser.add_argument("contracts_csv", type=Path, help="Cached normalized contract CSV.")
    contract_parser.add_argument(
        "output_csv", type=Path, help="Contract-enriched roster CSV output."
    )
    contract_parser.add_argument(
        "--audit-csv", type=Path, help="Optional contract matching audit CSV."
    )
    normalize_contract_parser = subparsers.add_parser(
        "normalize-nhl-contracts",
        help="Normalize a permitted cached NHL contract export with historical snapshot checks.",
    )
    normalize_contract_parser.add_argument(
        "input_csv", type=Path, help="Cached raw contract CSV export."
    )
    normalize_contract_parser.add_argument(
        "output_csv", type=Path, help="Normalized contract CSV output."
    )
    normalize_contract_parser.add_argument(
        "--snapshot-date", required=True, help="Source snapshot date in YYYY-MM-DD."
    )
    normalize_contract_parser.add_argument(
        "--metadata-json",
        required=True,
        type=Path,
        help="Source metadata sidecar with snapshot, access basis, and input checksum.",
    )
    normalize_contract_parser.add_argument(
        "--audit-csv", type=Path, help="Optional row-level normalization audit CSV."
    )
    demo_export_parser = subparsers.add_parser(
        "export-demo-package",
        help="Build board-ready demo exports for a single draft class.",
    )
    demo_export_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    demo_export_parser.add_argument(
        "output_dir", type=Path, help="Directory for demo export artifacts."
    )
    demo_export_parser.add_argument(
        "--team-depth-csv", type=Path, help="Optional NHL/AHL depth CSV for team-fit analysis."
    )
    demo_export_parser.add_argument(
        "--team-id", default="", help="Optional NHL team abbreviation for team-fit analysis."
    )
    demo_export_parser.add_argument(
        "--advanced-stats-csv", type=Path, help="Optional normalized advanced_stat_lines.csv."
    )
    demo_site_parser = subparsers.add_parser(
        "build-demo-site",
        help="Build a self-contained HTML demo app for a single draft class.",
    )
    demo_site_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    demo_site_parser.add_argument(
        "output_dir", type=Path, help="Directory for demo site artifacts."
    )
    demo_site_parser.add_argument(
        "--team-depth-csv", type=Path, help="Optional NHL/AHL depth CSV for team-fit analysis."
    )
    demo_site_parser.add_argument(
        "--team-id", default="", help="Optional NHL team abbreviation for team-fit analysis."
    )
    demo_site_parser.add_argument(
        "--advanced-stats-csv", type=Path, help="Optional normalized advanced_stat_lines.csv."
    )
    demo_readiness_parser = subparsers.add_parser(
        "build-demo-readiness",
        help="Build the demo site plus data-gap and modeling sanity reports.",
    )
    demo_readiness_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    demo_readiness_parser.add_argument(
        "output_dir", type=Path, help="Directory for demo and report artifacts."
    )
    demo_readiness_parser.add_argument(
        "--team-depth-csv", type=Path, help="Optional NHL/AHL depth CSV for team-fit analysis."
    )
    demo_readiness_parser.add_argument(
        "--team-id", default="", help="Optional NHL team abbreviation for team-fit analysis."
    )
    demo_readiness_parser.add_argument(
        "--advanced-stats-csv", type=Path, help="Optional normalized advanced_stat_lines.csv."
    )
    demo_readiness_parser.add_argument(
        "--gap-top-n",
        type=int,
        default=35,
        help="Number of priority low-evidence players to include in the data-gap report.",
    )
    demo_readiness_parser.add_argument(
        "--movement-top-n",
        type=int,
        default=40,
        help="Number of largest board-vs-consensus movements to include in the modeling report.",
    )
    demo_gaps_parser = subparsers.add_parser(
        "report-demo-gaps",
        help="Prioritize low-evidence players from a generated demo package.",
    )
    demo_gaps_parser.add_argument(
        "demo_output_dir", type=Path, help="Directory with board.csv and manifest.json."
    )
    demo_gaps_parser.add_argument(
        "output_dir", type=Path, help="Directory for gap report artifacts."
    )
    demo_gaps_parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of priority low-evidence players to write.",
    )
    demo_modeling_parser = subparsers.add_parser(
        "report-demo-modeling",
        help="Compare a generated demo board against consensus ordering.",
    )
    demo_modeling_parser.add_argument(
        "demo_output_dir", type=Path, help="Directory with board.csv and manifest.json."
    )
    demo_modeling_parser.add_argument(
        "output_dir", type=Path, help="Directory for modeling sanity artifacts."
    )
    demo_modeling_parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of largest board-vs-consensus movements to write.",
    )
    demo_sanity_parser = subparsers.add_parser(
        "report-demo-sanity",
        help="Build a focused top-board, role, and story-player sanity report.",
    )
    demo_sanity_parser.add_argument(
        "demo_output_dir", type=Path, help="Directory with board.csv and players.json."
    )
    demo_sanity_parser.add_argument(
        "output_dir", type=Path, help="Directory for demo sanity artifacts."
    )
    demo_acceptance_parser = subparsers.add_parser(
        "report-demo-acceptance",
        help="Run pass/fail business-demo acceptance checks against generated artifacts.",
    )
    demo_acceptance_parser.add_argument(
        "demo_output_dir", type=Path, help="Directory with board.csv, players.json, and index.html."
    )
    demo_acceptance_parser.add_argument(
        "output_dir", type=Path, help="Directory for demo acceptance artifacts."
    )
    etl_parser = subparsers.add_parser(
        "etl-draft-year",
        help="Run draft-year ETL with optional Elite Prospects enrichment.",
    )
    etl_parser.add_argument("output_dir", type=Path, help="Output root for ETL artifacts.")
    etl_parser.add_argument("--draft-year", type=int, required=True, help="NHL draft year.")
    etl_parser.add_argument(
        "--base-dir",
        type=Path,
        help="Existing normalized base dataset directory. Omit when generating from raw HockeyDB HTML.",
    )
    etl_parser.add_argument(
        "--nhl-draft-json",
        type=Path,
        help="Cached official NHL draft-picks JSON used to generate the base dataset.",
    )
    etl_parser.add_argument(
        "--hockeydb-draft-html",
        type=Path,
        help="Optional local HockeyDB draft HTML file used to generate the base dataset.",
    )
    etl_parser.add_argument(
        "--hockeydb-player-pages-dir",
        type=Path,
        help="Optional directory of cached HockeyDB player HTML pages for richer base enrichment.",
    )
    etl_parser.add_argument(
        "--eliteprospects-csv",
        type=Path,
        help="Optional Elite Prospects CSV export to import and merge into the base dataset.",
    )
    etl_parser.add_argument(
        "--timing",
        default="pre_draft",
        choices=("pre_draft", "post_draft"),
        help="Default timing for imported EP stat rows.",
    )
    etl_parser.add_argument(
        "--replace-timing",
        default="pre_draft",
        help="Base stat-line timing to replace for matched players during EP merge.",
    )
    etl_parser.add_argument(
        "--match-map",
        type=Path,
        help="Optional reviewed match map CSV for EP merge.",
    )
    etl_parser.add_argument(
        "--match-template-output",
        type=Path,
        help="Optional path for generated EP match-map template.",
    )
    etl_parser.add_argument(
        "--candidate-count",
        type=int,
        default=3,
        help="Number of closest base-player candidates to include in the template.",
    )
    range_etl_parser = subparsers.add_parser(
        "etl-draft-range",
        help="Plan or run resumable ETL for a manifest of draft classes.",
    )
    range_etl_parser.add_argument(
        "manifest_path", type=Path, help="CSV manifest with one row per draft class."
    )
    range_etl_parser.add_argument(
        "report_dir", type=Path, help="Output directory for batch run reports."
    )
    range_etl_parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Root used to resolve relative paths in the manifest.",
    )
    range_etl_parser.add_argument(
        "--output-root",
        type=Path,
        help="Default per-class ETL output root. Defaults to data/processed/draft_classes.",
    )
    range_etl_parser.add_argument(
        "--start-year", type=int, help="Optional inclusive first draft year."
    )
    range_etl_parser.add_argument(
        "--end-year", type=int, help="Optional inclusive last draft year."
    )
    range_etl_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write readiness reports without running any class ETL.",
    )
    range_etl_parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild classes whose required final tables already exist.",
    )
    range_etl_parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at the first class failure instead of recording it and continuing.",
    )
    collect_drafts_parser = subparsers.add_parser(
        "collect-nhl-draft-range",
        help="Cache official NHL draft-pick payloads for an inclusive year range.",
    )
    collect_drafts_parser.add_argument("cache_dir", type=Path, help="Raw JSON cache root.")
    collect_drafts_parser.add_argument("--start-year", type=int, required=True)
    collect_drafts_parser.add_argument("--end-year", type=int, required=True)
    collect_drafts_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Replace existing cached payloads.",
    )
    collect_leagues_parser = subparsers.add_parser(
        "collect-league-sources",
        help="Cache enabled league-stat sources from a reviewed CSV manifest.",
    )
    collect_leagues_parser.add_argument("manifest_path", type=Path)
    collect_leagues_parser.add_argument("--project-root", type=Path, default=Path("."))
    collect_leagues_parser.add_argument("--start-year", type=int)
    collect_leagues_parser.add_argument("--end-year", type=int)
    collect_leagues_parser.add_argument(
        "--adapter",
        action="append",
        choices=SUPPORTED_ADAPTERS,
        help="Only collect the selected adapter; repeat to select more than one.",
    )
    collect_leagues_parser.add_argument("--refresh", action="store_true")
    collect_leagues_parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Retry discovered backlog sources that are disabled because no cache exists.",
    )
    collect_leagues_parser.add_argument("--fail-fast", action="store_true")
    enrich_leagues_parser = subparsers.add_parser(
        "enrich-draft-range-leagues",
        help="Apply cached league-stat sources to normalized draft classes.",
    )
    enrich_leagues_parser.add_argument("manifest_path", type=Path)
    enrich_leagues_parser.add_argument("class_root", type=Path)
    enrich_leagues_parser.add_argument("report_dir", type=Path)
    enrich_leagues_parser.add_argument("--project-root", type=Path, default=Path("."))
    enrich_leagues_parser.add_argument("--start-year", type=int, required=True)
    enrich_leagues_parser.add_argument("--end-year", type=int, required=True)
    enrich_leagues_parser.add_argument("--force", action="store_true")
    enrich_leagues_parser.add_argument("--fail-fast", action="store_true")
    league_pipeline_parser = subparsers.add_parser(
        "run-league-pipeline",
        help="Discover, optionally collect, enrich, and audit league data in one resumable run.",
    )
    league_pipeline_parser.add_argument("manifest_path", type=Path)
    league_pipeline_parser.add_argument("class_root", type=Path)
    league_pipeline_parser.add_argument("output_dir", type=Path)
    league_pipeline_parser.add_argument("--project-root", type=Path, default=Path("."))
    league_pipeline_parser.add_argument(
        "--europe-catalog",
        type=Path,
        default=Path("data/reference/europe_league_source_catalog.csv"),
    )
    league_pipeline_parser.add_argument("--start-year", type=int, required=True)
    league_pipeline_parser.add_argument("--end-year", type=int, required=True)
    league_pipeline_parser.add_argument("--collect", action="store_true")
    league_pipeline_parser.add_argument("--refresh", action="store_true")
    league_pipeline_parser.add_argument("--force", action="store_true")
    league_pipeline_parser.add_argument("--fail-fast", action="store_true")
    discover_chl_parser = subparsers.add_parser(
        "discover-chl-sources",
        help="Generate historical CHL source rows from cached official season catalogs.",
    )
    discover_chl_parser.add_argument("output_path", type=Path)
    discover_chl_parser.add_argument(
        "--catalog",
        action="append",
        required=True,
        help="Catalog as league,local_html_path (repeat for OHL, WHL, and QMJHL).",
    )
    discover_chl_parser.add_argument("--cache-root", type=Path, required=True)
    discover_chl_parser.add_argument("--project-root", type=Path, default=Path("."))
    discover_chl_parser.add_argument("--start-year", type=int, required=True)
    discover_chl_parser.add_argument("--end-year", type=int, required=True)
    collect_ushl_catalog_parser = subparsers.add_parser(
        "collect-ushl-catalog",
        help="Cache the official public USHL HockeyTech season catalog.",
    )
    collect_ushl_catalog_parser.add_argument("output_path", type=Path)
    collect_ushl_catalog_parser.add_argument("--refresh", action="store_true")
    discover_ushl_parser = subparsers.add_parser(
        "discover-ushl-sources",
        help="Add historical USHL skater and goalie feeds to a league-source manifest.",
    )
    discover_ushl_parser.add_argument("manifest_path", type=Path)
    discover_ushl_parser.add_argument("--catalog", type=Path, required=True)
    discover_ushl_parser.add_argument("--cache-root", type=Path, required=True)
    discover_ushl_parser.add_argument("--project-root", type=Path, default=Path("."))
    discover_ushl_parser.add_argument("--start-year", type=int, required=True)
    discover_ushl_parser.add_argument("--end-year", type=int, required=True)
    discover_ncaa_parser = subparsers.add_parser(
        "discover-ncaa-sources",
        help="Add NCAA national skater and goalie sources to a league manifest.",
    )
    discover_ncaa_parser.add_argument("manifest_path", type=Path)
    discover_ncaa_parser.add_argument("--cache-root", type=Path, required=True)
    discover_ncaa_parser.add_argument("--project-root", type=Path, default=Path("."))
    discover_ncaa_parser.add_argument("--start-year", type=int, required=True)
    discover_ncaa_parser.add_argument("--end-year", type=int, required=True)
    discover_europe_parser = subparsers.add_parser(
        "discover-europe-sources",
        help="Merge reviewed Swedish, Finnish, and Russian sources into a league manifest.",
    )
    discover_europe_parser.add_argument("manifest_path", type=Path)
    discover_europe_parser.add_argument("--catalog", type=Path, required=True)
    discover_europe_parser.add_argument("--project-root", type=Path, default=Path("."))
    discover_europe_parser.add_argument("--start-year", type=int, required=True)
    discover_europe_parser.add_argument("--end-year", type=int, required=True)
    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate the consensus baseline against a normalized historical CSV.",
    )
    evaluate_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or a directory of normalized CSV tables.",
    )
    evaluate_parser.add_argument(
        "--baseline",
        choices=(
            "consensus",
            "projection",
            "adjusted-production",
            "contextual",
            "role-aware",
            "role-specific-hybrid",
            "hybrid",
        ),
        default="consensus",
        help="Baseline scorer to evaluate.",
    )
    evaluate_parser.add_argument(
        "--precision-n",
        type=int,
        default=10,
        help="Number of top-ranked players to use for precision@N.",
    )

    args = parser.parse_args()
    if args.command == "demo":
        run_demo()
    elif args.command == "scaffold-demo-class":
        run_scaffold_demo_class(args.draft_year)
    elif args.command == "audit-demo-class":
        run_audit_demo_class(args.draft_year)
    elif args.command == "import-eliteprospects":
        run_import_eliteprospects(
            args.export_path,
            args.output_dir,
            draft_year=args.draft_year,
            timing=args.timing,
        )
    elif args.command == "import-eliteprospects-pdf":
        run_import_eliteprospects_pdf(
            args.pdf_path,
            args.output_dir,
            draft_year=args.draft_year,
            page_start=args.page_start,
            page_end=args.page_end,
            profile_limit=args.profile_limit,
            index_page_start=args.index_page_start,
            index_page_end=args.index_page_end,
            vision_missing_tool_grades=args.vision_missing_tool_grades,
            vision_model=args.vision_model,
            pdftoppm_path=args.pdftoppm_path,
            vision_render_dpi=args.vision_render_dpi,
            env_file=args.env_file,
        )
    elif args.command == "overlay-eliteprospects-pdf-demo":
        run_overlay_eliteprospects_pdf_demo(
            args.base_dir,
            args.ep_pdf_dir,
            args.output_dir,
            fuzzy_threshold=args.fuzzy_threshold,
        )
    elif args.command == "validate-eliteprospects":
        run_validate_eliteprospects(args.export_path)
    elif args.command == "merge-eliteprospects":
        run_merge_eliteprospects(
            args.base_dir,
            args.eliteprospects_dir,
            args.output_dir,
            replace_timing=args.replace_timing,
            match_map=args.match_map,
        )
    elif args.command == "report-merge-quality":
        run_report_merge_quality(
            args.base_dir,
            args.source_dir,
            args.merged_dir,
            source_name=args.source_name,
            timing=args.timing,
        )
    elif args.command == "generate-match-map-template":
        run_generate_match_map_template(
            args.base_dir,
            args.unmatched_source_players,
            args.output_path,
            candidate_count=args.candidate_count,
        )
    elif args.command == "process-eliteprospects":
        run_process_eliteprospects(
            args.export_path,
            args.base_dir,
            args.source_output_dir,
            args.merged_output_dir,
            draft_year=args.draft_year,
            timing=args.timing,
            replace_timing=args.replace_timing,
            match_map=args.match_map,
            match_template_output=args.match_template_output,
            candidate_count=args.candidate_count,
        )
    elif args.command == "enrich-wikipedia-bio":
        run_enrich_wikipedia_bio(
            args.base_dir,
            args.output_dir,
            limit=args.limit,
            request_delay_seconds=args.request_delay_seconds,
            enable_search_fallback=args.enable_search_fallback,
            progress_every=args.progress_every,
            cache_dir=args.cache_dir,
        )
    elif args.command == "enrich-chl-stats":
        run_enrich_chl_stats(args.base_dir, args.output_dir, sources=args.source)
    elif args.command == "enrich-ushl-stats":
        run_enrich_ushl_stats(args.base_dir, args.output_dir, sources=args.source)
    elif args.command == "enrich-open-stats-csv":
        run_enrich_open_stats_csv(
            args.base_dir,
            args.output_dir,
            sources=args.source,
            allow_new_leagues=args.allow_new_leagues,
        )
    elif args.command == "enrich-wikipedia-career-stats":
        run_enrich_wikipedia_career_stats(
            args.base_dir,
            args.output_dir,
            season=args.season,
            cache_dir=args.cache_dir,
            request_delay_seconds=args.request_delay_seconds,
        )
    elif args.command == "enrich-puckpedia-stats":
        run_enrich_puckpedia_stats(
            args.base_dir,
            args.output_dir,
            season=args.season,
            cache_dir=args.cache_dir,
            request_delay_seconds=args.request_delay_seconds,
            limit=args.limit,
        )
    elif args.command == "export-feature-table":
        run_export_feature_table(args.data_path, args.output_path)
    elif args.command == "evaluate-role-models":
        run_evaluate_role_models(
            args.data_path,
            feature_output=args.feature_output,
            model_output=args.model_output,
            precision_n=args.precision_n,
        )
    elif args.command == "report-historical-validation":
        run_report_historical_validation(
            args.data_path,
            args.output_dir,
            precision_n=args.precision_n,
            top_n=args.top_n,
        )
    elif args.command == "report-team-depth":
        run_report_team_depth(args.roster_csv, args.output_dir)
    elif args.command == "audit-team-systems":
        run_audit_team_systems(args.roster_csv, args.demo_output_dir, args.output_dir)
    elif args.command == "audit-prospect-stats":
        run_audit_prospect_stats(args.output_dir, args.dataset_dirs, draft_year=args.draft_year)
    elif args.command == "report-ingestion-plan":
        run_report_ingestion_plan(
            args.manifest_csv, args.output_dir, project_root=args.project_root
        )
    elif args.command == "audit-league-ingestion":
        run_audit_league_ingestion(
            args.class_root,
            args.output_dir,
            start_year=args.start_year,
            end_year=args.end_year,
        )
    elif args.command == "audit-russian-coverage":
        run_audit_russian_coverage(
            args.dataset_dir,
            args.output_dir,
            draft_year=args.draft_year,
        )
    elif args.command == "report-codex-usage":
        run_report_codex_usage(args.run_log_csv, args.output_dir)
    elif args.command == "audit-codex-routing":
        run_audit_codex_routing(args.output_dir, project_root=args.project_root)
    elif args.command == "report-codex-context-routes":
        run_report_codex_context_routes(
            args.manifest_csv, args.output_dir, project_root=args.project_root
        )
    elif args.command == "report-codex-task-routing":
        run_report_codex_task_routing(args.manifest_csv, args.context_routes_csv, args.output_dir)
    elif args.command == "create-preseason-roster-proxy":
        run_create_preseason_roster_proxy(
            args.roster_csv,
            args.data_path,
            args.output_csv,
            audit_csv=args.audit_csv,
        )
    elif args.command == "merge-roster-csvs":
        run_merge_roster_csvs(
            args.output_csv,
            args.input_csvs,
            keep_duplicates=args.keep_duplicates,
            resolve_cross_org_assignments=args.resolve_cross_org_assignments,
            nhl_season=args.nhl_season,
            assignment_cache_dir=args.assignment_cache_dir,
        )
    elif args.command == "normalize-roster-snapshot":
        run_normalize_roster_snapshot(
            args.input_csv,
            args.output_csv,
            snapshot_date=args.snapshot_date,
            metadata_json=args.metadata_json,
            audit_csv=args.audit_csv,
        )
    elif args.command == "build-point-in-time-roster":
        run_build_point_in_time_roster(
            args.base_roster_csv,
            args.snapshot_csv,
            args.output_csv,
            expected_snapshot_date=args.snapshot_date,
            audit_csv=args.audit_csv,
        )
    elif args.command == "import-ahl-rosters":
        run_import_ahl_rosters(
            args.output_csv,
            season_id=args.season_id,
            season_label=args.season_label,
            minimum_games=args.minimum_games,
            reference_date=args.reference_date,
        )
    elif args.command == "import-nhl-rosters":
        run_import_nhl_rosters(
            args.output_csv,
            team_codes=args.teams,
            season=args.season,
            game_type=args.game_type,
            roster_json_dir=args.roster_json_dir,
            stats_json_dir=args.stats_json_dir,
            cache_json_dir=args.cache_json_dir,
        )
    elif args.command == "enrich-roster-contracts":
        run_enrich_roster_contracts(
            args.roster_csv,
            args.contracts_csv,
            args.output_csv,
            audit_csv=args.audit_csv,
        )
    elif args.command == "normalize-nhl-contracts":
        run_normalize_nhl_contracts(
            args.input_csv,
            args.output_csv,
            snapshot_date=args.snapshot_date,
            metadata_json=args.metadata_json,
            audit_csv=args.audit_csv,
        )
    elif args.command == "export-demo-package":
        run_export_demo_package(
            args.data_path,
            args.output_dir,
            team_depth_csv=args.team_depth_csv,
            team_id=args.team_id,
            advanced_stats_csv=args.advanced_stats_csv,
        )
    elif args.command == "build-demo-site":
        run_build_demo_site(
            args.data_path,
            args.output_dir,
            team_depth_csv=args.team_depth_csv,
            team_id=args.team_id,
            advanced_stats_csv=args.advanced_stats_csv,
        )
    elif args.command == "build-demo-readiness":
        run_build_demo_readiness(
            args.data_path,
            args.output_dir,
            gap_top_n=args.gap_top_n,
            movement_top_n=args.movement_top_n,
            team_depth_csv=args.team_depth_csv,
            team_id=args.team_id,
            advanced_stats_csv=args.advanced_stats_csv,
        )
    elif args.command == "report-demo-gaps":
        run_report_demo_gaps(args.demo_output_dir, args.output_dir, top_n=args.top_n)
    elif args.command == "report-demo-modeling":
        run_report_demo_modeling(args.demo_output_dir, args.output_dir, top_n=args.top_n)
    elif args.command == "report-demo-sanity":
        run_report_demo_sanity(args.demo_output_dir, args.output_dir)
    elif args.command == "report-demo-acceptance":
        run_report_demo_acceptance(args.demo_output_dir, args.output_dir)
    elif args.command == "etl-draft-year":
        run_etl_draft_year(
            args.base_dir,
            args.output_dir,
            draft_year=args.draft_year,
            nhl_draft_json=args.nhl_draft_json,
            hockeydb_draft_html=args.hockeydb_draft_html,
            hockeydb_player_pages_dir=args.hockeydb_player_pages_dir,
            eliteprospects_csv=args.eliteprospects_csv,
            timing=args.timing,
            replace_timing=args.replace_timing,
            match_map=args.match_map,
            match_template_output=args.match_template_output,
            candidate_count=args.candidate_count,
        )
    elif args.command == "etl-draft-range":
        run_etl_draft_range(
            args.manifest_path,
            args.report_dir,
            project_root=args.project_root,
            output_root=args.output_root,
            start_year=args.start_year,
            end_year=args.end_year,
            dry_run=args.dry_run,
            force=args.force,
            continue_on_error=not args.fail_fast,
        )
    elif args.command == "collect-nhl-draft-range":
        run_collect_nhl_draft_range(
            args.cache_dir,
            start_year=args.start_year,
            end_year=args.end_year,
            refresh=args.refresh,
        )
    elif args.command == "collect-league-sources":
        run_collect_league_sources(
            args.manifest_path,
            project_root=args.project_root,
            start_year=args.start_year,
            end_year=args.end_year,
            refresh=args.refresh,
            include_disabled=args.include_disabled,
            adapters=set(args.adapter or []),
            continue_on_error=not args.fail_fast,
        )
    elif args.command == "enrich-draft-range-leagues":
        run_enrich_draft_range_leagues(
            args.manifest_path,
            args.class_root,
            args.report_dir,
            project_root=args.project_root,
            start_year=args.start_year,
            end_year=args.end_year,
            force=args.force,
            continue_on_error=not args.fail_fast,
        )
    elif args.command == "run-league-pipeline":
        run_operational_league_pipeline(
            args.manifest_path,
            args.class_root,
            args.output_dir,
            project_root=args.project_root,
            europe_catalog=args.europe_catalog,
            start_year=args.start_year,
            end_year=args.end_year,
            collect=args.collect,
            refresh=args.refresh,
            force=args.force,
            continue_on_error=not args.fail_fast,
        )
    elif args.command == "discover-chl-sources":
        run_discover_chl_sources(
            args.output_path,
            args.catalog,
            cache_root=args.cache_root,
            project_root=args.project_root,
            start_year=args.start_year,
            end_year=args.end_year,
        )
    elif args.command == "collect-ushl-catalog":
        output = collect_ushl_season_catalog(args.output_path, refresh=args.refresh)
        print(f"# USHL season catalog\nCatalog: {output}")
    elif args.command == "discover-ushl-sources":
        run_discover_ushl_sources(
            args.manifest_path,
            catalog_path=args.catalog,
            cache_root=args.cache_root,
            project_root=args.project_root,
            start_year=args.start_year,
            end_year=args.end_year,
        )
    elif args.command == "discover-ncaa-sources":
        run_discover_ncaa_sources(
            args.manifest_path,
            cache_root=args.cache_root,
            project_root=args.project_root,
            start_year=args.start_year,
            end_year=args.end_year,
        )
    elif args.command == "discover-europe-sources":
        run_discover_europe_sources(
            args.manifest_path,
            catalog_path=args.catalog,
            project_root=args.project_root,
            start_year=args.start_year,
            end_year=args.end_year,
        )
    elif args.command == "evaluate":
        run_evaluate(args.data_path, baseline=args.baseline, precision_n=args.precision_n)


def run_demo() -> None:
    prospects = sample_prospects()
    team = sample_team_context()
    projections = project_board(prospects)
    scouting = {prospect.player_id: extract_scouting_features(prospect) for prospect in prospects}
    board = rank_board(prospects, projections, scouting, team)
    prospects_by_id = {prospect.player_id: prospect for prospect in prospects}

    print(f"# Team-adjusted board: {team.name}\n")
    for rank, rec in enumerate(board, start=1):
        prospect = prospects_by_id[rec.player_id]
        print(
            f"{rank}. {prospect.name} ({prospect.position}, {prospect.league}) "
            f"adjusted={rec.adjusted_value:.3f} recommendation={rec.recommendation}"
        )

    top = board[0]
    top_prospect = prospects_by_id[top.player_id]
    print("\n# Top Player Card\n")
    print(
        render_player_card(
            prospect=top_prospect,
            projection=projections[top.player_id],
            scouting=scouting[top.player_id],
            recommendation=top,
        )
    )


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        value = strip_env_value(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


def strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def run_scaffold_demo_class(draft_year: int) -> None:
    project_root = Path(__file__).resolve().parents[2]
    paths = scaffold_demo_class(project_root, draft_year)
    print(f"# Demo class scaffold: {draft_year}")
    print(f"HockeyDB draft HTML target: {paths.hockeydb_draft_html}")
    print(f"HockeyDB player pages dir: {paths.hockeydb_player_pages_dir}")
    print(f"Elite Prospects CSV target: {paths.eliteprospects_csv}")
    print(f"Match map template: {paths.match_map_csv}")
    print(f"Featured players template: {paths.featured_players_csv}")
    print(f"Processed demo dir: {paths.processed_demo_dir}")
    print(f"Demo outputs dir: {paths.outputs_dir}")


def run_audit_demo_class(draft_year: int) -> None:
    project_root = Path(__file__).resolve().parents[2]
    report = audit_demo_class(project_root, draft_year)
    print(format_demo_audit_report(report))


def run_audit_prospect_stats(
    output_dir: Path, dataset_dirs: list[Path], *, draft_year: int | None
) -> None:
    summary = write_prospect_stat_audit(output_dir, dataset_dirs, draft_year=draft_year)
    print(f"# Prospect stat audit: {draft_year or 'unknown draft year'}")
    print(f"Output directory: {output_dir}")
    print(f"Players: {summary['players']}")
    print(f"Stat lines: {summary['stat_lines']}")
    print(f"Goalies: {summary['goalies']}")
    print(f"Review flags: {summary['flags']}")


def run_report_ingestion_plan(manifest_csv: Path, output_dir: Path, *, project_root: Path) -> None:
    report = write_ingestion_plan_report(manifest_csv, output_dir, project_root=project_root)
    print(f"# Ingestion plan audit: {manifest_csv}")
    print(f"Output directory: {output_dir}")
    print(f"Source families: {len(report.audits)}")
    print(f"Ready: {report.ready_count}")
    print(f"Blocked: {report.blocked_count}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Audit CSV: {output_dir / 'source_family_audit.csv'}")


def run_audit_league_ingestion(
    class_root: Path,
    output_dir: Path,
    *,
    start_year: int,
    end_year: int,
) -> None:
    report = write_league_ingestion_audit(
        class_root,
        output_dir,
        start_year=start_year,
        end_year=end_year,
    )
    print(f"# League ingestion audit: {start_year}-{end_year}")
    print(f"Classes: {len(report.years)}")
    print(f"Issues: {len(report.issues)}")
    print(f"Report: {output_dir / 'summary.md'}")


def run_audit_russian_coverage(
    dataset_dir: Path,
    output_dir: Path,
    *,
    draft_year: int,
) -> None:
    report = write_russian_coverage_report(
        dataset_dir,
        output_dir,
        draft_year=draft_year,
    )
    print(f"# Russian league coverage: {draft_year}")
    print(f"Russian prospects: {report.russian_players}")
    print(f"Russian-league targets: {report.russian_league_targets}")
    print(f"Covered: {report.covered_players} ({report.coverage_pct:.1f}%)")
    print(f"External-league prospects: {report.external_league_players}")
    print(f"Missing: {report.missing_players}")
    print(f"Russian-family stat lines: {report.stat_lines}")
    print(f"Players with playoff evidence: {report.playoff_players}")
    print(f"Review queue: {output_dir / 'review_queue.csv'}")
    print(f"Summary: {output_dir / 'summary.md'}")


def run_report_codex_usage(run_log_csv: Path, output_dir: Path) -> None:
    report = write_codex_usage_report(run_log_csv, output_dir)
    print(f"# Codex usage report: {run_log_csv}")
    print(f"Output directory: {output_dir}")
    print(f"Runs: {report.run_count}")
    print(f"Compared tasks: {report.compared_task_count}")
    print(f"Total routed delta: {report.total_unit_delta_pct * 100:.1f}%")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Dashboard: {output_dir / 'index.html'}")


def run_audit_codex_routing(output_dir: Path, *, project_root: Path) -> None:
    report = write_codex_routing_audit(project_root, output_dir)
    print(f"# Codex routing audit: {project_root}")
    print(f"Output directory: {output_dir}")
    print(f"Status: {'pass' if report.passed else 'fail'}")
    print(f"Checks: {len(report.checks)}")
    print(f"Failed: {report.failed_count}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Checks CSV: {output_dir / 'checks.csv'}")


def run_report_codex_context_routes(
    manifest_csv: Path, output_dir: Path, *, project_root: Path
) -> None:
    report = write_codex_context_routes_report(manifest_csv, output_dir, project_root=project_root)
    print(f"# Codex context routes: {manifest_csv}")
    print(f"Output directory: {output_dir}")
    print(f"Status: {'pass' if report.passed else 'fail'}")
    print(f"Routes: {len(report.audits)}")
    print(f"Failed: {report.failed_count}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Routes CSV: {output_dir / 'context_routes.csv'}")


def run_report_codex_task_routing(
    manifest_csv: Path, context_routes_csv: Path, output_dir: Path
) -> None:
    report = write_codex_task_routing_report(manifest_csv, context_routes_csv, output_dir)
    print(f"# Codex task routing: {manifest_csv}")
    print(f"Output directory: {output_dir}")
    print(f"Status: {'pass' if report.passed else 'fail'}")
    print(f"Rules: {len(report.audits)}")
    print(f"Failed: {report.failed_count}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Rules CSV: {output_dir / 'task_routing.csv'}")


def run_import_eliteprospects(
    export_path: Path,
    output_dir: Path,
    *,
    draft_year: int,
    timing: str,
) -> None:
    normalized = write_eliteprospects_normalized_tables(
        export_path,
        output_dir,
        draft_year=draft_year,
        default_timing=timing,
    )
    print(f"# Elite Prospects import: {export_path}")
    print(f"Output directory: {output_dir}")
    print(f"Players written: {len(normalized.players)}")
    print(f"Season stat lines written: {len(normalized.season_stat_lines)}")


def run_import_eliteprospects_pdf(
    pdf_path: Path,
    output_dir: Path,
    *,
    draft_year: int,
    page_start: int,
    page_end: int | None,
    profile_limit: int | None,
    index_page_start: int | None,
    index_page_end: int | None,
    vision_missing_tool_grades: bool,
    vision_model: str | None,
    pdftoppm_path: str,
    vision_render_dpi: int,
    env_file: Path,
) -> None:
    load_env_file(env_file)
    resolved_vision_model = vision_model or os.environ.get(
        "OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL
    )
    resolved_pdftoppm_path = os.environ.get("PDFTOPPM_PATH", pdftoppm_path)
    normalized = write_eliteprospects_pdf_tables(
        pdf_path,
        output_dir,
        draft_year=draft_year,
        page_start=page_start,
        page_end=page_end,
        profile_limit=profile_limit,
        index_page_start=index_page_start,
        index_page_end=index_page_end,
        vision_missing_tool_grades=vision_missing_tool_grades,
        vision_model=resolved_vision_model,
        pdftoppm_path=resolved_pdftoppm_path,
        vision_render_dpi=vision_render_dpi,
    )
    print(f"# Elite Prospects PDF import: {pdf_path}")
    print(f"Output directory: {output_dir}")
    print(f"Profiles parsed: {len(normalized.profiles)}")
    print(f"Players written: {len(normalized.players)}")
    print(f"Season stat lines written: {len(normalized.season_stat_lines)}")
    print(f"Rankings written: {len(normalized.rankings)}")
    print(f"Tool grades written: {len(normalized.tool_grade_rows)}")
    print(f"Player index rows written: {len(normalized.index_rows)}")
    print(f"Vision usage rows written: {len(normalized.vision_usage_rows)}")
    if vision_missing_tool_grades:
        print(f"Vision model: {resolved_vision_model}")
    print(f"Profile sidecar: {output_dir / 'ep_pdf_profiles.csv'}")
    print(f"Extraction report: {output_dir / 'extraction_report.md'}")


def run_overlay_eliteprospects_pdf_demo(
    base_dir: Path,
    ep_pdf_dir: Path,
    output_dir: Path,
    *,
    fuzzy_threshold: float,
) -> None:
    summary = overlay_ep_pdf_demo_dataset(
        base_dir,
        ep_pdf_dir,
        output_dir,
        fuzzy_threshold=fuzzy_threshold,
    )
    report_path = output_dir / "ep_pdf_overlay_report.md"
    write_overlay_report(report_path, summary)
    print(f"# Elite Prospects PDF demo overlay: {base_dir}")
    print(f"EP PDF source: {ep_pdf_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Matched players: {summary.matched_players}/{summary.source_players}")
    print(f"Exact matches: {summary.exact_matches}")
    print(f"Alias matches: {summary.alias_matches}")
    print(f"Fuzzy matches: {summary.fuzzy_matches}")
    print(f"Added stat lines: {summary.added_stat_lines}")
    print(f"Augmented stat lines: {summary.augmented_stat_lines}")
    print(f"Output stat lines: {summary.output_stat_lines}")
    print(f"Reconciled duplicate stat groups: {summary.reconciled_duplicate_groups}")
    print(f"Stat conflict groups: {summary.reconciliation_conflict_groups}")
    print(f"EP profile rows: {summary.profile_rows}")
    print(f"EP tool-grade rows: {summary.tool_grade_rows}")
    print(f"Match audit: {output_dir / 'ep_pdf_match_audit.csv'}")
    print(f"Stat reconciliation audit: {output_dir / 'stat_line_reconciliation_audit.csv'}")
    print(f"Overlay report: {report_path}")


def run_validate_eliteprospects(export_path: Path) -> None:
    report = validate_eliteprospects_export(export_path)
    print(format_eliteprospects_validation_report(report))
    if report.has_errors:
        raise ValueError("Elite Prospects export has validation errors")


def run_merge_eliteprospects(
    base_dir: Path,
    eliteprospects_dir: Path,
    output_dir: Path,
    *,
    replace_timing: str,
    match_map: Path | None = None,
) -> None:
    summary = merge_normalized_source_tables(
        base_dir,
        eliteprospects_dir,
        output_dir,
        source_name="eliteprospects",
        replace_timing=replace_timing,
        match_map_path=match_map,
    )
    print(f"# Elite Prospects merge: {eliteprospects_dir}")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Base players: {summary.base_players}")
    print(f"Elite Prospects players: {summary.source_players}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Manual matches: {summary.manual_matches}")
    print(f"Name matches: {summary.name_matches}")
    print(f"Unmatched Elite Prospects players: {summary.unmatched_source_players}")
    print(f"Output season stat lines: {summary.output_stat_lines}")


def run_report_merge_quality(
    base_dir: Path,
    source_dir: Path,
    merged_dir: Path,
    *,
    source_name: str,
    timing: str,
) -> None:
    report = build_merge_quality_report(
        base_dir,
        source_dir,
        merged_dir,
        source_name=source_name,
        timing=timing,
    )
    print(format_merge_quality_report(report))


def run_generate_match_map_template(
    base_dir: Path,
    unmatched_source_players: Path,
    output_path: Path,
    *,
    candidate_count: int,
) -> None:
    rows = generate_match_map_template(
        base_dir,
        unmatched_source_players,
        output_path,
        candidate_count=candidate_count,
    )
    print(f"# Match map template: {output_path}")
    print(f"Unmatched source players: {len(rows)}")
    print("Review suggested candidates, then fill base_player_id for approved matches.")


def run_process_eliteprospects(
    export_path: Path,
    base_dir: Path,
    source_output_dir: Path,
    merged_output_dir: Path,
    *,
    draft_year: int,
    timing: str,
    replace_timing: str,
    match_map: Path | None,
    match_template_output: Path | None,
    candidate_count: int,
) -> None:
    validation = validate_eliteprospects_export(export_path)
    if validation.has_errors:
        print(format_eliteprospects_validation_report(validation))
        raise ValueError("Elite Prospects export has validation errors")

    normalized = write_eliteprospects_normalized_tables(
        export_path,
        source_output_dir,
        draft_year=draft_year,
        default_timing=timing,
    )
    summary = merge_normalized_source_tables(
        base_dir,
        source_output_dir,
        merged_output_dir,
        source_name="eliteprospects",
        replace_timing=replace_timing,
        match_map_path=match_map,
    )
    report = build_merge_quality_report(
        base_dir,
        source_output_dir,
        merged_output_dir,
        source_name="eliteprospects",
        timing=replace_timing or timing,
    )
    template_path = match_template_output or merged_output_dir / "match_map_template.csv"
    template_rows = generate_match_map_template(
        base_dir,
        merged_output_dir / "unmatched_source_players.csv",
        template_path,
        candidate_count=candidate_count,
    )

    print(f"# Elite Prospects processing: {export_path}")
    print(f"Imported players: {len(normalized.players)}")
    print(f"Imported season stat lines: {len(normalized.season_stat_lines)}")
    print(f"Merged output directory: {merged_output_dir}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Manual matches: {summary.manual_matches}")
    print(f"Name matches: {summary.name_matches}")
    print(f"Unmatched Elite Prospects players: {summary.unmatched_source_players}")
    print(f"Match map template: {template_path}")
    print(f"Template rows: {len(template_rows)}")
    print()
    print(format_merge_quality_report(report))


def run_enrich_wikipedia_bio(
    base_dir: Path,
    output_dir: Path,
    *,
    limit: int | None,
    request_delay_seconds: float,
    enable_search_fallback: bool,
    progress_every: int,
    cache_dir: Path | None,
) -> None:
    summary = enrich_wikipedia_bios(
        base_dir,
        output_dir,
        limit=limit,
        request_delay_seconds=request_delay_seconds,
        enable_search_fallback=enable_search_fallback,
        progress_every=progress_every,
        cache_dir=cache_dir,
    )
    print("# Wikipedia bio enrichment")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Players scanned: {summary.players_scanned}")
    print(f"Matched pages: {summary.matched_pages}")
    print(f"Players updated: {summary.players_updated}")
    print(f"Birth dates filled: {summary.birth_dates}")
    print(f"Heights filled: {summary.heights}")
    print(f"Weights filled: {summary.weights}")
    print(f"Handedness filled: {summary.handedness}")
    print(f"Match report: {summary.match_report_path}")


def run_enrich_chl_stats(base_dir: Path, output_dir: Path, *, sources: list[str]) -> None:
    parsed_sources = [parse_chl_source(value) for value in sources]
    summary = enrich_chl_stats(base_dir, output_dir, parsed_sources)
    print("# CHL stats enrichment")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Players scanned: {summary.players_scanned}")
    print(f"Source stat rows: {summary.source_rows}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Output stat lines: {summary.output_stat_lines}")
    print(f"Match report: {summary.match_report_path}")


def parse_chl_source(value: str) -> ChlStatSource:
    parts = [part.strip() for part in value.split(",", 4)]
    if len(parts) not in (3, 4, 5):
        raise ValueError(
            "CHL source must be league,season,url[,local_html_path][,regular|playoffs]"
        )
    league, season, url = parts[:3]
    path = Path(parts[3]) if len(parts) >= 4 and parts[3] else None
    regular_season = True
    if len(parts) == 5 and parts[4]:
        if parts[4] not in ("regular", "playoffs"):
            raise ValueError("CHL source season type must be 'regular' or 'playoffs'")
        regular_season = parts[4] == "regular"
    return ChlStatSource(
        league=league,
        season=season,
        source_url=url,
        regular_season=regular_season,
        source_path=path,
    )


def run_enrich_ushl_stats(base_dir: Path, output_dir: Path, *, sources: list[str]) -> None:
    parsed_sources = [parse_ushl_source(value) for value in sources]
    summary = enrich_ushl_stats(base_dir, output_dir, parsed_sources)
    print("# USHL stats enrichment")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Players scanned: {summary.players_scanned}")
    print(f"Source stat rows: {summary.source_rows}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Output stat lines: {summary.output_stat_lines}")
    print(f"Match report: {summary.match_report_path}")


def parse_ushl_source(value: str) -> UShlStatSource:
    parts = [part.strip() for part in value.split(",", 3)]
    if len(parts) not in (3, 4):
        raise ValueError("USHL source must be season,season_id,regular|playoffs[,local_json_path]")
    season, season_id, season_type = parts[:3]
    if season_type not in ("regular", "playoffs"):
        raise ValueError("USHL season type must be 'regular' or 'playoffs'")
    path = Path(parts[3]) if len(parts) == 4 and parts[3] else None
    return UShlStatSource(
        season=season,
        season_id=season_id,
        regular_season=season_type == "regular",
        source_path=path,
    )


def run_enrich_open_stats_csv(
    base_dir: Path,
    output_dir: Path,
    *,
    sources: list[str],
    allow_new_leagues: bool = False,
) -> None:
    parsed_sources = [parse_open_stats_source(value) for value in sources]
    summary = enrich_open_stats_csv(
        base_dir, output_dir, parsed_sources, allow_new_leagues=allow_new_leagues
    )
    print("# Open stats CSV enrichment")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Allow new leagues: {'yes' if allow_new_leagues else 'no'}")
    print(f"Players scanned: {summary.players_scanned}")
    print(f"Source stat rows: {summary.source_rows}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Output stat lines: {summary.output_stat_lines}")
    print(f"Match report: {summary.match_report_path}")


def parse_open_stats_source(value: str) -> OpenStatsCsvSource:
    parts = [part.strip() for part in value.split(",", 4)]
    if len(parts) not in (3, 4, 5):
        raise ValueError(
            "open stats source must be csv_path,source_label,season[,league][,regular|playoffs]"
        )
    path_text, source, season = parts[:3]
    league = parts[3] if len(parts) >= 4 else ""
    regular_season = True
    if len(parts) == 5 and parts[4]:
        if parts[4] not in ("regular", "playoffs"):
            raise ValueError("open stats season type must be 'regular' or 'playoffs'")
        regular_season = parts[4] == "regular"
    return OpenStatsCsvSource(
        path=Path(path_text),
        source=source,
        season=season,
        league=league,
        regular_season=regular_season,
    )


def run_enrich_wikipedia_career_stats(
    base_dir: Path,
    output_dir: Path,
    *,
    season: str,
    cache_dir: Path | None,
    request_delay_seconds: float,
) -> None:
    summary = enrich_wikipedia_career_stats(
        base_dir,
        output_dir,
        season=season,
        cache_dir=cache_dir,
        request_delay_seconds=request_delay_seconds,
    )
    print("# Wikipedia career-stats enrichment")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Season: {season}")
    print(f"Players scanned: {summary.players_scanned}")
    print(f"Pages fetched: {summary.pages_fetched}")
    print(f"Source stat rows: {summary.source_rows}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Output stat lines: {summary.output_stat_lines}")
    print(f"Match report: {summary.match_report_path}")


def run_enrich_puckpedia_stats(
    base_dir: Path,
    output_dir: Path,
    *,
    season: str,
    cache_dir: Path | None,
    request_delay_seconds: float,
    limit: int | None,
) -> None:
    summary = enrich_puckpedia_stats(
        base_dir,
        output_dir,
        season=season,
        cache_dir=cache_dir,
        request_delay_seconds=request_delay_seconds,
        limit=limit,
    )
    print("# PuckPedia stats enrichment")
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Season: {season}")
    print(f"Players scanned: {summary.players_scanned}")
    print(f"Pages fetched: {summary.pages_fetched}")
    print(f"Source stat rows: {summary.source_rows}")
    print(f"Matched players: {summary.matched_players}")
    print(f"Output stat lines: {summary.output_stat_lines}")
    print(f"Match report: {summary.match_report_path}")


def run_export_feature_table(data_path: Path, output_path: Path) -> None:
    prospects = load_historical_prospects(data_path)
    rows = build_feature_rows(prospects, load_advanced_stat_summaries(data_path))
    write_feature_table(output_path, rows)
    print(f"# Feature table export: {output_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Feature rows written: {len(rows)}")


def run_evaluate_role_models(
    data_path: Path,
    *,
    feature_output: Path | None,
    model_output: Path | None,
    precision_n: int,
) -> None:
    prospects = load_historical_prospects(data_path)
    feature_rows, models, _, probability_report, board_report = evaluate_role_specific_models(
        prospects,
        precision_n=precision_n,
        advanced_stats=load_advanced_stat_summaries(data_path),
    )
    if feature_output is not None:
        write_feature_table(feature_output, feature_rows)
    if model_output is not None:
        write_model_summary(model_output, models)

    print(f"# Role-specific model evaluation: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    warning = outcome_validation_warning(prospects)
    if warning:
        print(warning)
    if feature_output is not None:
        print(f"Feature table: {feature_output}")
    if model_output is not None:
        print(f"Model summary: {model_output}")
    print(f"Precision@N: {precision_n}\n")
    print(format_evaluation_report(probability_report))
    print()
    print(format_board_order_report(board_report))


def run_export_demo_package(
    data_path: Path,
    output_dir: Path,
    *,
    team_depth_csv: Path | None = None,
    team_id: str = "",
    advanced_stats_csv: Path | None = None,
) -> None:
    prospects = load_historical_prospects(data_path)
    bundle = build_demo_export_bundle(
        prospects,
        team_depth_csv=team_depth_csv,
        team_id=team_id,
        advanced_stats=load_advanced_stat_summaries(advanced_stats_csv or data_path),
    )
    outputs = export_demo_package(output_dir, bundle)
    print(f"# Demo package export: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Board rows: {len(bundle.board_rows)}")
    print(f"Board CSV: {outputs['board']}")
    print(f"Compare CSV: {outputs['compare']}")
    print(f"Players JSON: {outputs['players']}")
    print(f"Manifest JSON: {outputs['manifest']}")
    print(f"Dataset status: {bundle.manifest['dataset_status']}")


def run_build_demo_site(
    data_path: Path,
    output_dir: Path,
    *,
    team_depth_csv: Path | None = None,
    team_id: str = "",
    advanced_stats_csv: Path | None = None,
) -> None:
    prospects = load_historical_prospects(data_path)
    bundle = build_demo_export_bundle(
        prospects,
        team_depth_csv=team_depth_csv,
        team_id=team_id,
        advanced_stats=load_advanced_stat_summaries(advanced_stats_csv or data_path),
    )
    outputs = export_demo_package(output_dir, bundle)
    site_path = write_demo_site(output_dir, bundle)
    brief = write_demo_meeting_brief(output_dir, bundle)
    print(f"# Demo site build: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Output directory: {output_dir}")
    print(f"Board CSV: {outputs['board']}")
    print(f"Players JSON: {outputs['players']}")
    print(f"Manifest JSON: {outputs['manifest']}")
    print(f"HTML site: {site_path}")
    print(f"Meeting brief HTML: {brief.html_path}")
    print(f"Meeting brief PDF: {brief.pdf_path}")
    print(f"Dataset status: {bundle.manifest['dataset_status']}")


def run_build_demo_readiness(
    data_path: Path,
    output_dir: Path,
    *,
    gap_top_n: int,
    movement_top_n: int,
    team_depth_csv: Path | None = None,
    team_id: str = "",
    advanced_stats_csv: Path | None = None,
) -> None:
    prospects = load_historical_prospects(data_path)
    bundle = build_demo_export_bundle(
        prospects,
        team_depth_csv=team_depth_csv,
        team_id=team_id,
        advanced_stats=load_advanced_stat_summaries(advanced_stats_csv or data_path),
    )
    outputs = export_demo_package(output_dir, bundle)
    site_path = write_demo_site(output_dir, bundle)
    brief = write_demo_meeting_brief(output_dir, bundle)
    reports_dir = output_dir / "reports"
    gap_report_dir = reports_dir / "data_gaps"
    modeling_report_dir = reports_dir / "modeling_sanity"
    sanity_report_dir = reports_dir / "demo_sanity"
    acceptance_report_dir = reports_dir / "demo_acceptance"
    gap_report = write_demo_gap_report(output_dir, gap_report_dir, top_n=gap_top_n)
    modeling_report = write_demo_modeling_report(
        output_dir, modeling_report_dir, top_n=movement_top_n
    )
    write_demo_sanity_report(output_dir, sanity_report_dir)
    acceptance_report = write_demo_acceptance_report(output_dir, acceptance_report_dir)

    print(f"# Demo readiness build: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Output directory: {output_dir}")
    print(f"Board CSV: {outputs['board']}")
    print(f"Players JSON: {outputs['players']}")
    print(f"Manifest JSON: {outputs['manifest']}")
    print(f"HTML site: {site_path}")
    print(f"Meeting brief HTML: {brief.html_path}")
    print(f"Meeting brief PDF: {brief.pdf_path}")
    print(f"Dataset status: {bundle.manifest['dataset_status']}")
    print(f"Low-evidence players: {len(gap_report.low_evidence_rows)}")
    print(f"Data-gap summary: {gap_report_dir / 'summary.md'}")
    print(f"Average board-vs-consensus movement: {modeling_report.avg_abs_delta:.1f}")
    print(f"Players moved 10+ slots: {modeling_report.moved_10_plus}")
    print(f"Modeling summary: {modeling_report_dir / 'summary.md'}")
    print(f"Demo sanity summary: {sanity_report_dir / 'summary.md'}")
    print(f"Demo acceptance: {'pass' if acceptance_report.passed else 'fail'}")
    print(f"Demo acceptance summary: {acceptance_report_dir / 'summary.md'}")


def run_report_demo_gaps(demo_output_dir: Path, output_dir: Path, *, top_n: int) -> None:
    report = write_demo_gap_report(demo_output_dir, output_dir, top_n=top_n)
    print(f"# Demo data gap report: {demo_output_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Low-evidence players: {len(report.low_evidence_rows)}")
    print(f"Priority rows written: {len(report.priority_rows)}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Priority CSV: {output_dir / 'priority_gaps.csv'}")


def run_report_demo_modeling(demo_output_dir: Path, output_dir: Path, *, top_n: int) -> None:
    report = write_demo_modeling_report(demo_output_dir, output_dir, top_n=top_n)
    print(f"# Demo modeling sanity report: {demo_output_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Average absolute movement: {report.avg_abs_delta:.1f}")
    print(f"Players moved 10+ slots: {report.moved_10_plus}")


def run_report_demo_sanity(demo_output_dir: Path, output_dir: Path) -> None:
    report = write_demo_sanity_report(demo_output_dir, output_dir)
    print(f"# Demo sanity report: {demo_output_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Top overall rows: {len(report.top_overall)}")
    print(f"Top defense rows: {len(report.top_defense)}")
    print(f"Top goalie rows: {len(report.top_goalies)}")
    print(f"Story checks: {len(report.story_rows)}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Story checks CSV: {output_dir / 'story_player_checks.csv'}")
    print(f"Biggest disagreements CSV: {output_dir / 'biggest_disagreements.csv'}")


def run_report_demo_acceptance(demo_output_dir: Path, output_dir: Path) -> None:
    report = write_demo_acceptance_report(demo_output_dir, output_dir)
    print(f"# Demo acceptance report: {demo_output_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Status: {'pass' if report.passed else 'fail'}")
    print(f"Checks: {len(report.checks)}")
    print(f"Failed: {report.failed_count}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Checks CSV: {output_dir / 'acceptance_checks.csv'}")


def run_etl_draft_year(
    base_dir: Path | None,
    output_dir: Path,
    *,
    draft_year: int,
    nhl_draft_json: Path | None = None,
    hockeydb_draft_html: Path | None = None,
    hockeydb_player_pages_dir: Path | None = None,
    eliteprospects_csv: Path | None,
    timing: str,
    replace_timing: str,
    match_map: Path | None,
    match_template_output: Path | None,
    candidate_count: int,
) -> None:
    config = DraftYearETLConfig(
        draft_year=draft_year,
        output_root=output_dir,
        base_dir=base_dir,
        nhl_draft_json=nhl_draft_json,
        hockeydb_draft_html=hockeydb_draft_html,
        hockeydb_player_pages_dir=hockeydb_player_pages_dir,
        eliteprospects_csv=eliteprospects_csv,
        match_map=match_map,
        match_template_output=match_template_output,
        timing=timing,
        replace_timing=replace_timing,
        candidate_count=candidate_count,
    )
    prepare_base_dataset(config)

    print(f"# Draft-year ETL: {draft_year}")
    print(f"Base input directory: {base_dir or nhl_draft_json or hockeydb_draft_html}")
    print(f"ETL output root: {output_dir}")
    print(f"Base snapshot: {config.base_output_dir}")

    if eliteprospects_csv is None:
        copy_dataset_directory(config.base_output_dir, config.final_output_dir)
        print("Elite Prospects enrichment: skipped")
        print(f"Final dataset: {config.final_output_dir}")
        return

    run_process_eliteprospects(
        eliteprospects_csv,
        config.base_output_dir,
        config.eliteprospects_output_dir,
        config.final_output_dir,
        draft_year=draft_year,
        timing=timing,
        replace_timing=replace_timing,
        match_map=match_map,
        match_template_output=config.resolve_match_template_output(),
        candidate_count=candidate_count,
    )
    print(f"Final dataset: {config.final_output_dir}")


def run_etl_draft_range(
    manifest_path: Path,
    report_dir: Path,
    *,
    project_root: Path,
    output_root: Path | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    continue_on_error: bool = True,
) -> None:
    specs = load_draft_class_manifest(
        manifest_path,
        project_root=project_root,
        output_root=output_root,
    )
    selected = filter_draft_class_specs(specs, start_year=start_year, end_year=end_year)
    report = execute_draft_range_etl(
        selected,
        executor=execute_draft_class_spec,
        report_dir=report_dir,
        dry_run=dry_run,
        force=force,
        continue_on_error=continue_on_error,
    )
    print(f"# Draft-range ETL: {manifest_path}")
    print(f"Classes selected: {len(selected)}")
    print(f"Mode: {'dry-run' if dry_run else 'execute'}")
    print(f"Completed or reusable: {report.ready_count}")
    print(f"Failed: {report.failed_count}")
    print(f"Blocked: {report.blocked_count}")
    print(f"Run report: {report_dir / 'summary.md'}")
    if not dry_run and (report.failed_count or report.blocked_count):
        raise RuntimeError(
            f"draft-range ETL incomplete: failed={report.failed_count}, "
            f"blocked={report.blocked_count}"
        )


def execute_draft_class_spec(spec: DraftClassETLSpec) -> None:
    use_normalized_base = spec.base_dir is not None and all(
        (spec.base_dir / name).is_file()
        for name in (
            "players.csv",
            "draft_selections.csv",
            "rankings.csv",
            "season_stat_lines.csv",
            "nhl_outcomes.csv",
        )
    )
    run_etl_draft_year(
        spec.base_dir if use_normalized_base else None,
        spec.output_dir,
        draft_year=spec.draft_year,
        nhl_draft_json=(
            spec.nhl_draft_json
            if not use_normalized_base and spec.nhl_draft_json and spec.nhl_draft_json.is_file()
            else None
        ),
        hockeydb_draft_html=None if use_normalized_base else spec.hockeydb_draft_html,
        hockeydb_player_pages_dir=(
            spec.hockeydb_player_pages_dir
            if spec.hockeydb_player_pages_dir and spec.hockeydb_player_pages_dir.is_dir()
            else None
        ),
        eliteprospects_csv=(
            spec.eliteprospects_csv
            if spec.eliteprospects_csv and spec.eliteprospects_csv.is_file()
            else None
        ),
        timing="pre_draft",
        replace_timing="pre_draft",
        match_map=spec.match_map if spec.match_map and spec.match_map.is_file() else None,
        match_template_output=spec.output_dir / "eliteprospects_match_map_template.csv",
        candidate_count=3,
    )


def run_collect_nhl_draft_range(
    cache_dir: Path,
    *,
    start_year: int,
    end_year: int,
    refresh: bool = False,
) -> None:
    results = collect_nhl_draft_range(
        cache_dir,
        start_year=start_year,
        end_year=end_year,
        refresh=refresh,
    )
    print(f"# NHL draft cache: {start_year}-{end_year}")
    for result in results:
        print(
            f"{result.draft_year}: {result.status}; "
            f"picks={result.pick_count}; path={result.cache_path}"
        )


def run_collect_league_sources(
    manifest_path: Path,
    *,
    project_root: Path,
    start_year: int | None,
    end_year: int | None,
    refresh: bool,
    include_disabled: bool,
    adapters: set[str],
    continue_on_error: bool,
) -> None:
    sources = filter_league_sources(
        load_league_source_manifest(manifest_path, project_root=project_root),
        start_year=start_year,
        end_year=end_year,
        include_disabled=include_disabled,
        adapters=adapters,
    )
    results = collect_league_sources(
        sources,
        refresh=refresh,
        continue_on_error=continue_on_error,
    )
    print(f"# League source cache: {manifest_path}")
    for result in results:
        print(
            f"{result.source_id}: {result.status}; bytes={result.byte_count}; "
            f"path={result.cache_path}; {result.detail}"
        )
    failed = sum(result.status == "failed" for result in results)
    if failed:
        raise RuntimeError(f"league source collection incomplete: failed={failed}")


def run_discover_chl_sources(
    output_path: Path,
    catalogs: list[str],
    *,
    cache_root: Path,
    project_root: Path,
    start_year: int,
    end_year: int,
) -> None:
    root = project_root.resolve()
    resolved_cache_root = cache_root if cache_root.is_absolute() else root / cache_root
    sources = []
    for value in catalogs:
        league, separator, path_text = value.partition(",")
        if not separator or not league.strip() or not path_text.strip():
            raise ValueError("CHL catalog must be league,local_html_path")
        catalog_path = Path(path_text.strip())
        if not catalog_path.is_absolute():
            catalog_path = root / catalog_path
        sources.extend(
            discover_chl_source_specs(
                catalog_path,
                league=league.strip(),
                cache_root=resolved_cache_root,
                start_year=start_year,
                end_year=end_year,
            )
        )
    output = write_league_source_manifest(
        output_path,
        sources,
        project_root=root,
    )
    print(f"# CHL source discovery: {start_year}-{end_year}")
    print(f"Catalogs: {len(catalogs)}")
    print(f"Sources discovered: {len(sources)}")
    print(f"Manifest: {output}")


def run_discover_ushl_sources(
    manifest_path: Path,
    *,
    catalog_path: Path,
    cache_root: Path,
    project_root: Path,
    start_year: int,
    end_year: int,
) -> None:
    root = project_root.resolve()
    catalog = catalog_path if catalog_path.is_absolute() else root / catalog_path
    cache = cache_root if cache_root.is_absolute() else root / cache_root
    discovered = discover_ushl_source_specs(
        catalog,
        cache_root=cache,
        start_year=start_year,
        end_year=end_year,
    )
    existing = (
        load_league_source_manifest(manifest_path, project_root=root)
        if manifest_path.is_file()
        else []
    )
    sources = merge_league_source_specs(existing, discovered, adapter="ushl")
    output = write_league_source_manifest(manifest_path, sources, project_root=root)
    print(f"# USHL source discovery: {start_year}-{end_year}")
    print(f"Sources discovered: {len(discovered)}")
    print(f"Enabled caches: {sum(source.enabled for source in discovered)}")
    print(f"Manifest: {output}")


def run_discover_ncaa_sources(
    manifest_path: Path,
    *,
    cache_root: Path,
    project_root: Path,
    start_year: int,
    end_year: int,
) -> None:
    root = project_root.resolve()
    cache = cache_root if cache_root.is_absolute() else root / cache_root
    discovered = discover_ncaa_source_specs(
        cache_root=cache,
        start_year=start_year,
        end_year=end_year,
    )
    existing = (
        load_league_source_manifest(manifest_path, project_root=root)
        if manifest_path.is_file()
        else []
    )
    sources = merge_league_source_specs(existing, discovered, adapter="ncaa")
    output = write_league_source_manifest(manifest_path, sources, project_root=root)
    print(f"# NCAA source discovery: {start_year}-{end_year}")
    print(f"Sources discovered: {len(discovered)}")
    print(f"Enabled caches: {sum(source.enabled for source in discovered)}")
    print(f"Manifest: {output}")


def run_discover_europe_sources(
    manifest_path: Path,
    *,
    catalog_path: Path,
    project_root: Path,
    start_year: int,
    end_year: int,
) -> None:
    root = project_root.resolve()
    catalog = catalog_path if catalog_path.is_absolute() else root / catalog_path
    discovered = discover_europe_source_specs(
        catalog,
        project_root=root,
        start_year=start_year,
        end_year=end_year,
    )
    existing = (
        load_league_source_manifest(manifest_path, project_root=root)
        if manifest_path.is_file()
        else []
    )
    sources = merge_league_source_specs(existing, discovered, adapter="europe")
    output = write_league_source_manifest(manifest_path, sources, project_root=root)
    print(f"# European source discovery: {start_year}-{end_year}")
    print(f"Sources discovered: {len(discovered)}")
    print(f"Enabled caches: {sum(source.enabled for source in discovered)}")
    print(f"Manifest: {output}")


def run_enrich_draft_range_leagues(
    manifest_path: Path,
    class_root: Path,
    report_dir: Path,
    *,
    project_root: Path,
    start_year: int,
    end_year: int,
    force: bool,
    continue_on_error: bool,
) -> None:
    sources = filter_league_sources(
        load_league_source_manifest(manifest_path, project_root=project_root),
        start_year=start_year,
        end_year=end_year,
    )
    report = run_league_enrichment_range(
        class_root,
        sources,
        report_dir=report_dir,
        start_year=start_year,
        end_year=end_year,
        force=force,
        continue_on_error=continue_on_error,
    )
    print(f"# Draft-range league enrichment: {start_year}-{end_year}")
    print(f"Sources selected: {len(sources)}")
    print(f"Failed classes: {report.failed_count}")
    print(f"Run report: {report_dir / 'summary.md'}")
    if report.failed_count:
        raise RuntimeError(f"league enrichment incomplete: failed={report.failed_count}")


def run_operational_league_pipeline(
    manifest_path: Path,
    class_root: Path,
    output_dir: Path,
    *,
    project_root: Path,
    europe_catalog: Path,
    start_year: int,
    end_year: int,
    collect: bool,
    refresh: bool,
    force: bool,
    continue_on_error: bool,
) -> None:
    summary = run_league_pipeline(
        manifest_path,
        class_root,
        output_dir,
        project_root=project_root,
        europe_catalog_path=europe_catalog,
        start_year=start_year,
        end_year=end_year,
        collect=collect,
        refresh=refresh,
        force=force,
        continue_on_error=continue_on_error,
    )
    print(f"# League ingestion pipeline: {start_year}-{end_year}")
    print(f"Ready sources: {summary.ready_sources}/{summary.discovered_sources}")
    print(f"Collection failures: {summary.collection_failures}")
    print(f"Enrichment failures: {summary.enrichment_failures}")
    print(f"Audit issues: {summary.audit_issues}")
    print(f"Run report: {output_dir / 'summary.md'}")
    if summary.enrichment_failures:
        raise RuntimeError(
            f"league ingestion incomplete: failed classes={summary.enrichment_failures}"
        )


def run_evaluate(data_path: Path, *, baseline: str = "consensus", precision_n: int = 10) -> None:
    prospects = load_historical_prospects(data_path)
    scores = score_historical_prospects(prospects, baseline=baseline)
    report = evaluate_historical_scores(prospects, scores, precision_n=precision_n)

    print(f"# {baseline.title()} baseline evaluation: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    warning = outcome_validation_warning(prospects)
    if warning:
        print(warning)
    print(f"Precision@N: {precision_n}\n")
    print(format_evaluation_report(report))


def run_report_historical_validation(
    data_path: Path,
    output_dir: Path,
    *,
    precision_n: int = 25,
    top_n: int = 25,
) -> None:
    prospects = load_historical_prospects(data_path)
    report = write_historical_validation_report(
        output_dir,
        prospects,
        data_path,
        precision_n=precision_n,
        top_n=top_n,
    )
    print(f"# Historical validation report: {data_path}")
    print(f"Prospects loaded: {report.prospect_count}")
    warning = outcome_validation_warning(prospects)
    if warning:
        print(warning)
    print(f"Summary CSV: {output_dir / 'summary.csv'}")
    print(f"Summary Markdown: {output_dir / 'summary.md'}")


def run_report_team_depth(roster_csv: Path, output_dir: Path) -> None:
    players = load_roster_csv(roster_csv)
    depth_rows = build_depth_rows(players)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_depth_csv(output_dir / "depth.csv", depth_rows)
    (output_dir / "summary.md").write_text(format_depth_markdown(depth_rows), encoding="utf-8")

    teams = sorted({player.team_id for player in players})
    print(f"# Team depth report: {roster_csv}")
    print(f"Roster players loaded: {len(players)}")
    print(f"Teams: {len(teams)}")
    print(f"Depth rows: {len(depth_rows)}")
    print(f"Depth CSV: {output_dir / 'depth.csv'}")
    print(f"Summary Markdown: {output_dir / 'summary.md'}")


def run_audit_team_systems(roster_csv: Path, demo_output_dir: Path, output_dir: Path) -> None:
    audit = write_team_system_audit(roster_csv, demo_output_dir, output_dir)
    print(f"# Team system audit: {roster_csv}")
    print(f"Team-bucket rows: {len(audit.team_rows)}")
    print(f"Goalie rows: {len(audit.goalie_rows)}")
    print(f"Review flags: {len(audit.flag_rows)}")
    print(f"Team bucket CSV: {output_dir / 'team_bucket_audit.csv'}")
    print(f"Goalie CSV: {output_dir / 'goalie_audit.csv'}")
    print(f"Review flags CSV: {output_dir / 'review_flags.csv'}")
    print(f"Roster reliability CSV: {output_dir / 'roster_reliability.csv'}")
    print(f"Summary Markdown: {output_dir / 'summary.md'}")


def run_create_preseason_roster_proxy(
    roster_csv: Path,
    data_path: Path,
    output_csv: Path,
    *,
    audit_csv: Path | None = None,
) -> None:
    players = load_roster_csv(roster_csv)
    prospects = load_historical_prospects(data_path)
    draft_names = {compact_name(prospect.name) for prospect in prospects}
    kept = []
    removed = []
    for player in players:
        if compact_name(player.player_name) in draft_names:
            removed.append(player)
        else:
            kept.append(player)

    write_roster_csv(output_csv, kept)
    if audit_csv is not None:
        write_preseason_proxy_audit(audit_csv, removed)

    print(f"# Preseason roster proxy: {roster_csv}")
    print(f"Draft-class players matched for removal: {len(removed)}")
    print(f"Roster players kept: {len(kept)}")
    print(f"Proxy roster CSV: {output_csv}")
    if audit_csv is not None:
        print(f"Removal audit CSV: {audit_csv}")


def write_preseason_proxy_audit(path: Path, players) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "team_id",
        "team_name",
        "league_level",
        "player_id",
        "player_name",
        "position",
        "age",
        "source",
        "source_id",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for player in players:
            writer.writerow(
                {
                    "team_id": player.team_id,
                    "team_name": player.team_name,
                    "league_level": player.league_level,
                    "player_id": player.player_id,
                    "player_name": player.player_name,
                    "position": player.position,
                    "age": f"{player.age:.1f}" if player.age else "",
                    "source": player.source,
                    "source_id": player.source_id,
                }
            )


def compact_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in decomposed if character.isascii() and character.isalnum()
    )


def run_merge_roster_csvs(
    output_csv: Path,
    input_csvs: list[Path],
    *,
    keep_duplicates: bool = False,
    resolve_cross_org_assignments: bool = False,
    nhl_season: str = "20242025",
    assignment_cache_dir: Path | None = None,
) -> None:
    players = []
    for input_csv in input_csvs:
        players.extend(load_roster_csv(input_csv))
    input_count = len(players)
    if resolve_cross_org_assignments:
        players = enrich_cross_organization_assignment_dates(
            players,
            nhl_season=nhl_season,
            cache_json_dir=assignment_cache_dir,
        )
    if not keep_duplicates:
        players = dedupe_roster_assignments(players)
    write_roster_csv(output_csv, players)
    print("# Merged roster CSV")
    print(f"Input files: {len(input_csvs)}")
    print(f"Input roster players: {input_count}")
    print(f"Roster players: {len(players)}")
    print(f"Duplicate assignment rows removed: {input_count - len(players)}")
    print(f"Output CSV: {output_csv}")


def run_normalize_roster_snapshot(
    input_csv: Path,
    output_csv: Path,
    *,
    snapshot_date: str,
    metadata_json: Path,
    audit_csv: Path | None,
) -> None:
    summary = normalize_roster_snapshot(
        input_csv,
        output_csv,
        snapshot_date=snapshot_date,
        metadata_json=metadata_json,
        audit_csv=audit_csv,
    )
    print("# Normalized roster rights snapshot")
    print(f"Input rows: {summary.input_rows}")
    print(f"Normalized rows: {summary.normalized_rows}")
    print(f"Rejected rows: {summary.rejected_rows}")
    print(f"Teams: {summary.teams}")
    print(f"Output CSV: {output_csv}")


def run_build_point_in_time_roster(
    base_roster_csv: Path,
    snapshot_csv: Path,
    output_csv: Path,
    *,
    expected_snapshot_date: str,
    audit_csv: Path | None,
) -> None:
    summary = build_point_in_time_roster(
        base_roster_csv,
        snapshot_csv,
        output_csv,
        expected_snapshot_date=expected_snapshot_date,
        audit_csv=audit_csv,
    )
    print("# Point-in-time organizational roster")
    print(f"Rights snapshot rows: {summary.source_rows}")
    print(f"Matched season-stat rows: {summary.matched_players}")
    print(f"Rights holders without season stats: {summary.sparse_players}")
    print(f"Excluded season-participation rows: {summary.excluded_base_players}")
    print(f"Output roster players: {summary.output_players}")
    print(f"Output CSV: {output_csv}")


def dedupe_roster_assignments(players):
    grouped = {}
    for player in players:
        key = (player.team_id.upper(), compact_name(player.player_name))
        grouped.setdefault(key, []).append(player)
    selected = [choose_roster_assignment(group) for group in grouped.values()]
    selected = remove_cross_organization_pipeline_duplicates(selected)
    return sorted(
        selected,
        key=lambda player: (
            player.team_id,
            player.league_level,
            player.position,
            player.player_name,
        ),
    )


def remove_cross_organization_pipeline_duplicates(players):
    grouped = {}
    for player in players:
        grouped.setdefault(compact_name(player.player_name), []).append(player)
    kept = []
    for group in grouped.values():
        identity_group = [
            player
            for player in group
            if any(same_roster_identity(player, other) for other in group if other is not player)
        ]
        if len({player.team_id for player in identity_group}) <= 1:
            kept.extend(group)
            continue
        dated = [player for player in identity_group if player.last_game_date]
        latest_date = max((player.last_game_date for player in dated), default="")
        latest = [player for player in dated if player.last_game_date == latest_date]
        authoritative_team_ids = {player.team_id for player in latest}
        if len(dated) != len(identity_group) or not latest_date or len(authoritative_team_ids) != 1:
            kept.extend(
                replace(
                    player,
                    assignment_confidence="low",
                    roster_status="cross_org_assignment_unresolved",
                )
                if player in identity_group
                else player
                for player in group
            )
            continue
        authoritative_team_id = next(iter(authoritative_team_ids))
        for player in group:
            if player not in identity_group or player.team_id == authoritative_team_id:
                kept.append(
                    replace(
                        player,
                        assignment_confidence="high",
                        roster_status="latest_season_assignment",
                    )
                    if player in identity_group
                    else player
                )
    return kept


def same_roster_identity(left, right) -> bool:
    if compact_name(left.player_name) != compact_name(right.player_name):
        return False
    if not left.age or not right.age:
        return False
    return abs(left.age - right.age) <= 1.0


def choose_roster_assignment(players):
    if len(players) == 1:
        return players[0]
    nhl_players = [player for player in players if player.league_level == "NHL"]
    ahl_players = [player for player in players if player.league_level == "AHL"]
    if nhl_players and ahl_players:
        best_nhl = max(nhl_players, key=roster_assignment_strength)
        best_ahl = max(ahl_players, key=roster_assignment_strength)
        if (
            best_nhl.position == "G"
            and best_nhl.age < 24.5
            and best_nhl.games <= 10
            and best_ahl.games >= best_nhl.games
        ):
            return best_ahl
        if (
            best_nhl.position != "G"
            and best_nhl.age < 23.5
            and best_nhl.games <= 10
            and best_ahl.games >= best_nhl.games
        ):
            return best_ahl
        if best_nhl.games >= 20 or best_nhl.league_level == "NHL":
            return best_nhl
        return best_ahl
    return max(players, key=roster_assignment_strength)


def roster_assignment_strength(player) -> tuple[float, int, int]:
    level_weight = 2 if player.league_level == "NHL" else 1
    return (level_weight, player.games, player.points)


def run_import_ahl_rosters(
    output_csv: Path,
    *,
    season_id: str,
    season_label: str,
    minimum_games: int,
    reference_date: date,
) -> None:
    summary = import_ahl_rosters(
        output_csv,
        season_id=season_id,
        season_label=season_label,
        minimum_games=minimum_games,
        reference_date=reference_date,
    )
    print("# AHL roster import")
    print(f"Season: {summary.season_label} ({summary.season_id})")
    print(f"AHL teams loaded: {summary.teams_loaded}")
    print(f"Skater stat rows: {summary.skaters_loaded}")
    print(f"Goalie stat rows: {summary.goalies_loaded}")
    print(f"Roster detail rows: {summary.roster_detail_players}")
    print(f"Normalized roster players: {summary.normalized_players}")
    print(f"Roster CSV: {summary.output_csv}")


def run_import_nhl_rosters(
    output_csv: Path,
    *,
    team_codes: list[str] | None,
    season: str,
    game_type: int,
    roster_json_dir: Path | None,
    stats_json_dir: Path | None,
    cache_json_dir: Path | None,
) -> None:
    summary = import_nhl_rosters(
        output_csv,
        team_codes=team_codes,
        season=season,
        game_type=game_type,
        roster_json_dir=roster_json_dir,
        stats_json_dir=stats_json_dir,
        cache_json_dir=cache_json_dir,
    )
    print("# NHL roster import")
    print(f"Teams requested: {summary.teams_requested}")
    print(f"Teams loaded: {summary.teams_loaded}")
    print(f"Roster players: {summary.roster_players}")
    print(f"Teams with stats: {summary.stats_teams_loaded}")
    print(f"Roster CSV: {summary.output_csv}")


def run_enrich_roster_contracts(
    roster_csv: Path,
    contracts_csv: Path,
    output_csv: Path,
    *,
    audit_csv: Path | None,
) -> None:
    summary = enrich_roster_contracts(roster_csv, contracts_csv, output_csv, audit_csv=audit_csv)
    print("# NHL contract overlay")
    print(f"Roster players: {summary.roster_players}")
    print(f"Contract rows: {summary.contract_rows}")
    print(f"Matched roster players: {summary.matched_players}")
    print(f"Eligible NHL players: {summary.eligible_nhl_players}")
    print(f"NHL contract coverage: {summary.nhl_coverage:.1%}")
    print(f"Unmatched contract rows: {summary.unmatched_contracts}")
    print(f"Ambiguous contract rows: {summary.ambiguous_contracts}")
    print(f"Roster CSV: {output_csv}")
    if audit_csv is not None:
        print(f"Contract match audit: {audit_csv}")


def run_normalize_nhl_contracts(
    input_csv: Path,
    output_csv: Path,
    *,
    snapshot_date: str,
    metadata_json: Path,
    audit_csv: Path | None,
) -> None:
    summary = normalize_contract_export(
        input_csv,
        output_csv,
        snapshot_date=snapshot_date,
        metadata_json=metadata_json,
        audit_csv=audit_csv,
    )
    print("# NHL contract normalization")
    print(f"Input rows: {summary.input_rows}")
    print(f"Normalized rows: {summary.normalized_rows}")
    print(f"Rejected rows: {summary.rejected_rows}")
    print(f"Future-signing rows rejected: {summary.future_signing_rows}")
    print(f"Conflicting duplicate rows rejected: {summary.conflicting_duplicate_rows}")
    print(f"Normalized contract CSV: {output_csv}")
    if audit_csv is not None:
        print(f"Normalization audit: {audit_csv}")


def load_historical_prospects(data_path: Path):
    if data_path.is_dir():
        return load_normalized_historical_prospects(data_path)
    return load_historical_prospects_csv(data_path)


def score_historical_prospects(prospects: list, *, baseline: str) -> dict[str, float]:
    if baseline == "consensus":
        return consensus_scores(prospects)
    if baseline == "projection":
        projection_inputs = [prospect.to_projection_prospect() for prospect in prospects]
        return projection_scores(project_board(projection_inputs))
    if baseline == "adjusted-production":
        return adjusted_production_scores(prospects)
    if baseline == "contextual":
        return contextual_scores(prospects)
    if baseline == "role-aware":
        return role_aware_scores(prospects)
    if baseline == "role-specific-hybrid":
        return role_specific_hybrid_scores(prospects)
    if baseline == "hybrid":
        projection_inputs = [prospect.to_projection_prospect() for prospect in prospects]
        return weighted_hybrid_scores(
            [
                (consensus_scores(prospects), 0.5),
                (projection_scores(project_board(projection_inputs)), 0.3),
                (adjusted_production_scores(prospects), 0.2),
            ]
        )
    raise ValueError(f"unsupported baseline: {baseline}")


def outcome_validation_warning(prospects: list) -> str:
    if not prospects:
        return ""
    outcomes = [prospect.outcome for prospect in prospects if prospect.outcome is not None]
    if not outcomes:
        return (
            "Validation warning: no NHL outcome rows are available; use this as demo analysis only."
        )
    if all(outcome.nhl_games == 0 and outcome.nhl_points == 0 for outcome in outcomes):
        return (
            "Validation warning: all NHL outcomes are zero; recent-class metrics are not predictive validation. "
            "Use evidence depth and source coverage for this dataset."
        )
    return ""


def format_evaluation_report(report: dict[str, dict[str, float]]) -> str:
    sections: list[str] = []
    for section_name in ("nhler", "impact", "bust", "rank"):
        metrics = report[section_name]
        lines = [f"## {section_name}"]
        for metric_name, value in metrics.items():
            lines.append(f"- {metric_name}: {value:.3f}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_board_order_report(report: dict[str, dict[str, float]]) -> str:
    sections = ["## board_order"]
    for section_name, metrics in report.items():
        sections.append(f"### {section_name}")
        for metric_name, value in metrics.items():
            sections.append(f"- {metric_name}: {value:.3f}")
    return "\n".join(sections)


def copy_dataset_directory(source_dir: Path, destination_dir: Path) -> None:
    if not source_dir.exists():
        raise ValueError(f"missing dataset directory: {source_dir}")
    source = source_dir.resolve()
    destination = destination_dir.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError(
            f"dataset source and destination must not overlap: {source} -> {destination}"
        )

    temporary = destination.with_name(f".{destination.name}.tmp")
    previous = destination.with_name(f".{destination.name}.previous")
    if temporary.exists():
        shutil.rmtree(temporary)
    if previous.exists():
        shutil.rmtree(previous)
    shutil.copytree(source, temporary)
    if destination.exists():
        destination.rename(previous)
    try:
        temporary.rename(destination)
    except Exception:
        if previous.exists() and not destination.exists():
            previous.rename(destination)
        raise
    if previous.exists():
        shutil.rmtree(previous)


def prepare_base_dataset(config: DraftYearETLConfig) -> None:
    if config.base_dir is not None:
        copy_dataset_directory(config.base_dir, config.base_output_dir)
        return
    if config.nhl_draft_json is not None:
        generate_nhl_draft_base_tables(
            config.nhl_draft_json,
            config.base_output_dir,
            draft_year=config.draft_year,
        )
        return
    if config.hockeydb_draft_html is None:
        raise ValueError(
            "one of base_dir, --nhl-draft-json, or --hockeydb-draft-html must be provided"
        )
    generate_hockeydb_base_tables(
        HockeyDbBaseETLConfig(
            draft_year=config.draft_year,
            draft_html_path=config.hockeydb_draft_html,
            output_dir=config.base_output_dir,
            player_pages_dir=config.hockeydb_player_pages_dir,
        )
    )


if __name__ == "__main__":
    main()
