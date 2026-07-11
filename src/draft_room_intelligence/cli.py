"""Command-line entry point for the PoC."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from draft_room_intelligence.data.chl_stats import ChlStatSource, enrich_chl_stats
from draft_room_intelligence.data.demo_data import (
    audit_demo_class,
    format_demo_audit_report,
    scaffold_demo_class,
)
from draft_room_intelligence.data.eliteprospects_csv import (
    format_eliteprospects_validation_report,
    validate_eliteprospects_export,
    write_eliteprospects_normalized_tables,
)
from draft_room_intelligence.data.etl_config import DraftYearETLConfig
from draft_room_intelligence.data.historical_csv import load_historical_prospects_csv
from draft_room_intelligence.data.hockeydb_base import (
    HockeyDbBaseETLConfig,
    generate_hockeydb_base_tables,
)
from draft_room_intelligence.data.merge_quality import (
    build_merge_quality_report,
    format_merge_quality_report,
)
from draft_room_intelligence.data.normalized_merge import (
    generate_match_map_template,
    merge_normalized_source_tables,
)
from draft_room_intelligence.data.normalized_tables import load_normalized_historical_prospects
from draft_room_intelligence.data.open_stats_csv import OpenStatsCsvSource, enrich_open_stats_csv
from draft_room_intelligence.data.puckpedia_stats import enrich_puckpedia_stats
from draft_room_intelligence.data.wikipedia_bio import enrich_wikipedia_bios
from draft_room_intelligence.data.wikipedia_career_stats import enrich_wikipedia_career_stats
from draft_room_intelligence.data.ushl_stats import UShlStatSource, enrich_ushl_stats
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
from draft_room_intelligence.modeling.feature_table import build_feature_rows, write_feature_table
from draft_room_intelligence.modeling.role_models import (
    evaluate_role_specific_models,
    write_model_summary,
)
from draft_room_intelligence.reports.demo_export import (
    build_demo_export_bundle,
    export_demo_package,
)
from draft_room_intelligence.reports.demo_gaps import write_demo_gap_report
from draft_room_intelligence.reports.demo_modeling import write_demo_modeling_report
from draft_room_intelligence.reports.demo_site import write_demo_site
from draft_room_intelligence.reports.historical_validation import write_historical_validation_report
from draft_room_intelligence.optimization.board import rank_board
from draft_room_intelligence.projection.baseline import project_board
from draft_room_intelligence.reports.player_card import render_player_card
from draft_room_intelligence.sample_data import sample_prospects, sample_team_context
from draft_room_intelligence.scouting.extraction import extract_scouting_features


def main() -> None:
    parser = argparse.ArgumentParser(prog="draft-room-intel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo", help="Run the sample projection + team-fit pipeline.")
    scaffold_demo_parser = subparsers.add_parser(
        "scaffold-demo-class",
        help="Create the local folder and template structure for a demo draft class.",
    )
    scaffold_demo_parser.add_argument("--draft-year", type=int, required=True, help="NHL draft year.")
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
    import_ep_parser.add_argument("output_dir", type=Path, help="Directory for normalized CSV output.")
    import_ep_parser.add_argument("--draft-year", type=int, required=True, help="NHL draft year.")
    import_ep_parser.add_argument(
        "--timing",
        default="pre_draft",
        choices=("pre_draft", "post_draft"),
        help="Default timing for stat rows without a timing column.",
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
    merge_ep_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
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
    quality_parser.add_argument("base_dir", type=Path, help="Original normalized dataset directory.")
    quality_parser.add_argument("source_dir", type=Path, help="Normalized source dataset directory.")
    quality_parser.add_argument("merged_dir", type=Path, help="Merged normalized dataset directory.")
    quality_parser.add_argument("--source-name", default="eliteprospects", help="Source label to audit.")
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
    process_ep_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
    process_ep_parser.add_argument("source_output_dir", type=Path, help="Directory for imported EP tables.")
    process_ep_parser.add_argument("merged_output_dir", type=Path, help="Directory for merged output.")
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
    wiki_bio_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
    wiki_bio_parser.add_argument("output_dir", type=Path, help="Directory for enriched normalized output.")
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
    chl_stats_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
    chl_stats_parser.add_argument("output_dir", type=Path, help="Directory for CHL-enriched output.")
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
    ushl_stats_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
    ushl_stats_parser.add_argument("output_dir", type=Path, help="Directory for USHL-enriched output.")
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
    open_stats_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
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
    wiki_career_stats_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
    wiki_career_stats_parser.add_argument("output_dir", type=Path, help="Directory for enriched output.")
    wiki_career_stats_parser.add_argument("--season", required=True, help="Season to extract, e.g. 2024-25.")
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
    puckpedia_stats_parser.add_argument("base_dir", type=Path, help="Existing normalized dataset directory.")
    puckpedia_stats_parser.add_argument("output_dir", type=Path, help="Directory for enriched output.")
    puckpedia_stats_parser.add_argument("--season", required=True, help="Season to extract, e.g. 2024-25.")
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
    feature_table_parser.add_argument("output_path", type=Path, help="CSV path for exported features.")
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
    validation_parser.add_argument("output_dir", type=Path, help="Directory for validation report artifacts.")
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
    demo_export_parser = subparsers.add_parser(
        "export-demo-package",
        help="Build board-ready demo exports for a single draft class.",
    )
    demo_export_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    demo_export_parser.add_argument("output_dir", type=Path, help="Directory for demo export artifacts.")
    demo_site_parser = subparsers.add_parser(
        "build-demo-site",
        help="Build a self-contained HTML demo app for a single draft class.",
    )
    demo_site_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    demo_site_parser.add_argument("output_dir", type=Path, help="Directory for demo site artifacts.")
    demo_readiness_parser = subparsers.add_parser(
        "build-demo-readiness",
        help="Build the demo site plus data-gap and modeling sanity reports.",
    )
    demo_readiness_parser.add_argument(
        "data_path",
        type=Path,
        help="Path to a wide historical CSV or normalized dataset directory.",
    )
    demo_readiness_parser.add_argument("output_dir", type=Path, help="Directory for demo and report artifacts.")
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
    demo_gaps_parser.add_argument("demo_output_dir", type=Path, help="Directory with board.csv and manifest.json.")
    demo_gaps_parser.add_argument("output_dir", type=Path, help="Directory for gap report artifacts.")
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
    demo_modeling_parser.add_argument("demo_output_dir", type=Path, help="Directory with board.csv and manifest.json.")
    demo_modeling_parser.add_argument("output_dir", type=Path, help="Directory for modeling sanity artifacts.")
    demo_modeling_parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of largest board-vs-consensus movements to write.",
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
        choices=("consensus", "projection", "adjusted-production", "contextual", "role-aware", "role-specific-hybrid", "hybrid"),
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
    elif args.command == "export-demo-package":
        run_export_demo_package(args.data_path, args.output_dir)
    elif args.command == "build-demo-site":
        run_build_demo_site(args.data_path, args.output_dir)
    elif args.command == "build-demo-readiness":
        run_build_demo_readiness(
            args.data_path,
            args.output_dir,
            gap_top_n=args.gap_top_n,
            movement_top_n=args.movement_top_n,
        )
    elif args.command == "report-demo-gaps":
        run_report_demo_gaps(args.demo_output_dir, args.output_dir, top_n=args.top_n)
    elif args.command == "report-demo-modeling":
        run_report_demo_modeling(args.demo_output_dir, args.output_dir, top_n=args.top_n)
    elif args.command == "etl-draft-year":
        run_etl_draft_year(
            args.base_dir,
            args.output_dir,
            draft_year=args.draft_year,
            hockeydb_draft_html=args.hockeydb_draft_html,
            hockeydb_player_pages_dir=args.hockeydb_player_pages_dir,
            eliteprospects_csv=args.eliteprospects_csv,
            timing=args.timing,
            replace_timing=args.replace_timing,
            match_map=args.match_map,
            match_template_output=args.match_template_output,
            candidate_count=args.candidate_count,
        )
    elif args.command == "evaluate":
        run_evaluate(args.data_path, baseline=args.baseline, precision_n=args.precision_n)


def run_demo() -> None:
    prospects = sample_prospects()
    team = sample_team_context()
    projections = project_board(prospects)
    scouting = {
        prospect.player_id: extract_scouting_features(prospect)
        for prospect in prospects
    }
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
        raise ValueError("CHL source must be league,season,url[,local_html_path][,regular|playoffs]")
    league, season, url = parts[:3]
    path = Path(parts[3]) if len(parts) >= 4 and parts[3] else None
    regular_season = True
    if len(parts) == 5 and parts[4]:
        if parts[4] not in ("regular", "playoffs"):
            raise ValueError("CHL source season type must be 'regular' or 'playoffs'")
        regular_season = parts[4] == "regular"
    return ChlStatSource(league=league, season=season, source_url=url, regular_season=regular_season, source_path=path)


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
    summary = enrich_open_stats_csv(base_dir, output_dir, parsed_sources, allow_new_leagues=allow_new_leagues)
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
        raise ValueError("open stats source must be csv_path,source_label,season[,league][,regular|playoffs]")
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
    rows = build_feature_rows(prospects)
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


def run_export_demo_package(data_path: Path, output_dir: Path) -> None:
    prospects = load_historical_prospects(data_path)
    bundle = build_demo_export_bundle(prospects)
    outputs = export_demo_package(output_dir, bundle)
    print(f"# Demo package export: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Board rows: {len(bundle.board_rows)}")
    print(f"Board CSV: {outputs['board']}")
    print(f"Compare CSV: {outputs['compare']}")
    print(f"Players JSON: {outputs['players']}")
    print(f"Manifest JSON: {outputs['manifest']}")
    print(f"Dataset status: {bundle.manifest['dataset_status']}")


def run_build_demo_site(data_path: Path, output_dir: Path) -> None:
    prospects = load_historical_prospects(data_path)
    bundle = build_demo_export_bundle(prospects)
    outputs = export_demo_package(output_dir, bundle)
    site_path = write_demo_site(output_dir, bundle)
    print(f"# Demo site build: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Output directory: {output_dir}")
    print(f"Board CSV: {outputs['board']}")
    print(f"Players JSON: {outputs['players']}")
    print(f"Manifest JSON: {outputs['manifest']}")
    print(f"HTML site: {site_path}")
    print(f"Dataset status: {bundle.manifest['dataset_status']}")


def run_build_demo_readiness(
    data_path: Path,
    output_dir: Path,
    *,
    gap_top_n: int,
    movement_top_n: int,
) -> None:
    prospects = load_historical_prospects(data_path)
    bundle = build_demo_export_bundle(prospects)
    outputs = export_demo_package(output_dir, bundle)
    site_path = write_demo_site(output_dir, bundle)
    reports_dir = output_dir / "reports"
    gap_report_dir = reports_dir / "data_gaps"
    modeling_report_dir = reports_dir / "modeling_sanity"
    gap_report = write_demo_gap_report(output_dir, gap_report_dir, top_n=gap_top_n)
    modeling_report = write_demo_modeling_report(output_dir, modeling_report_dir, top_n=movement_top_n)

    print(f"# Demo readiness build: {data_path}")
    print(f"Prospects loaded: {len(prospects)}")
    print(f"Output directory: {output_dir}")
    print(f"Board CSV: {outputs['board']}")
    print(f"Players JSON: {outputs['players']}")
    print(f"Manifest JSON: {outputs['manifest']}")
    print(f"HTML site: {site_path}")
    print(f"Dataset status: {bundle.manifest['dataset_status']}")
    print(f"Low-evidence players: {len(gap_report.low_evidence_rows)}")
    print(f"Data-gap summary: {gap_report_dir / 'summary.md'}")
    print(f"Average board-vs-consensus movement: {modeling_report.avg_abs_delta:.1f}")
    print(f"Players moved 10+ slots: {modeling_report.moved_10_plus}")
    print(f"Modeling summary: {modeling_report_dir / 'summary.md'}")


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
    print(f"10+ slot moves with high/medium evidence: {report.high_or_medium_moved_10_plus}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Largest movements CSV: {output_dir / 'largest_movements.csv'}")


def run_etl_draft_year(
    base_dir: Path | None,
    output_dir: Path,
    *,
    draft_year: int,
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
    print(f"Base input directory: {base_dir or hockeydb_draft_html}")
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
        return "Validation warning: no NHL outcome rows are available; use this as demo analysis only."
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
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)


def prepare_base_dataset(config: DraftYearETLConfig) -> None:
    if config.base_dir is not None:
        copy_dataset_directory(config.base_dir, config.base_output_dir)
        return
    if config.hockeydb_draft_html is None:
        raise ValueError("either base_dir or --hockeydb-draft-html must be provided")
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
