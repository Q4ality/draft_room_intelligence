#!/usr/bin/env python3
"""Helper workflow for preparing a single-class demo dataset."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from draft_room_intelligence.cli import run_audit_demo_class
from draft_room_intelligence.cli import run_build_demo_readiness
from draft_room_intelligence.cli import run_etl_draft_year
from draft_room_intelligence.cli import run_scaffold_demo_class
from draft_room_intelligence.data.demo_data import demo_class_paths


def main() -> None:
    parser = argparse.ArgumentParser(prog="demo_data_workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scaffold_parser = subparsers.add_parser("scaffold", help="Create year-specific demo directories and templates.")
    scaffold_parser.add_argument("--draft-year", type=int, required=True)

    audit_parser = subparsers.add_parser("audit", help="Audit local readiness for a draft-year demo.")
    audit_parser.add_argument("--draft-year", type=int, required=True)

    browser_plan_parser = subparsers.add_parser(
        "browser-plan",
        help="Print a browser-assisted collection plan with target paths and staging guidance.",
    )
    browser_plan_parser.add_argument("--draft-year", type=int, required=True)

    downloads_parser = subparsers.add_parser(
        "stage-downloads",
        help="Stage likely draft HTML / EP CSV files from a downloads directory into expected repo paths.",
    )
    downloads_parser.add_argument("--draft-year", type=int, required=True)
    downloads_parser.add_argument("--downloads-dir", type=Path, default=Path.home() / "Downloads")

    draft_html_parser = subparsers.add_parser(
        "stage-draft-html",
        help="Copy a locally saved HockeyDB draft HTML file into the expected repo path.",
    )
    draft_html_parser.add_argument("--draft-year", type=int, required=True)
    draft_html_parser.add_argument("--source", type=Path, required=True)

    ep_parser = subparsers.add_parser(
        "stage-eliteprospects-csv",
        help="Copy an Elite Prospects export CSV into the expected repo path.",
    )
    ep_parser.add_argument("--draft-year", type=int, required=True)
    ep_parser.add_argument("--source", type=Path, required=True)

    pages_parser = subparsers.add_parser(
        "stage-player-pages",
        help="Copy locally saved HockeyDB player pages into the expected repo folder.",
    )
    pages_parser.add_argument("--draft-year", type=int, required=True)
    pages_parser.add_argument("--source-dir", type=Path, required=True)

    etl_parser = subparsers.add_parser("run-etl", help="Run draft-year ETL from staged demo inputs.")
    etl_parser.add_argument("--draft-year", type=int, required=True)
    etl_parser.add_argument("--with-eliteprospects", action="store_true")

    demo_parser = subparsers.add_parser("build-demo", help="Build the demo site from the final ETL dataset.")
    demo_parser.add_argument("--draft-year", type=int, required=True)

    args = parser.parse_args()

    if args.command == "scaffold":
        run_scaffold_demo_class(args.draft_year)
    elif args.command == "audit":
        run_audit_demo_class(args.draft_year)
    elif args.command == "browser-plan":
        print_browser_plan(args.draft_year)
    elif args.command == "stage-downloads":
        stage_downloads(args.draft_year, args.downloads_dir)
    elif args.command == "stage-draft-html":
        paths = demo_class_paths(REPO_ROOT, args.draft_year)
        stage_file(args.source, paths.hockeydb_draft_html)
        print(f"Staged draft HTML: {paths.hockeydb_draft_html}")
    elif args.command == "stage-eliteprospects-csv":
        paths = demo_class_paths(REPO_ROOT, args.draft_year)
        stage_file(args.source, paths.eliteprospects_csv)
        print(f"Staged Elite Prospects CSV: {paths.eliteprospects_csv}")
    elif args.command == "stage-player-pages":
        paths = demo_class_paths(REPO_ROOT, args.draft_year)
        stage_player_pages(args.source_dir, paths.hockeydb_player_pages_dir)
        print(f"Staged player pages into: {paths.hockeydb_player_pages_dir}")
    elif args.command == "run-etl":
        paths = demo_class_paths(REPO_ROOT, args.draft_year)
        eliteprospects_csv = paths.eliteprospects_csv if args.with_eliteprospects and paths.eliteprospects_csv.exists() else None
        run_etl_draft_year(
            None,
            paths.processed_demo_dir,
            draft_year=args.draft_year,
            hockeydb_draft_html=paths.hockeydb_draft_html,
            hockeydb_player_pages_dir=paths.hockeydb_player_pages_dir,
            eliteprospects_csv=eliteprospects_csv,
            timing="pre_draft",
            replace_timing="pre_draft",
            match_map=paths.match_map_csv if paths.match_map_csv.exists() else None,
            match_template_output=None,
            candidate_count=3,
        )
    elif args.command == "build-demo":
        paths = demo_class_paths(REPO_ROOT, args.draft_year)
        dataset_dir = paths.processed_demo_dir / "final"
        output_dir = paths.outputs_dir
        if not dataset_dir.exists() and paths.latest_processed_demo_dir is not None:
            dataset_dir = paths.latest_processed_demo_dir / "final"
            if paths.latest_outputs_dir is not None:
                output_dir = paths.latest_outputs_dir
        run_build_demo_readiness(
            dataset_dir,
            output_dir,
            gap_top_n=35,
            movement_top_n=40,
        )


def stage_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Source file does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def stage_player_pages(source_dir: Path, destination_dir: Path) -> None:
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(source_dir.glob("*.html")):
        shutil.copy2(path, destination_dir / path.name)
        copied += 1
    if copied == 0:
        raise ValueError(f"No .html files found in source directory: {source_dir}")


def print_browser_plan(draft_year: int) -> None:
    paths = demo_class_paths(REPO_ROOT, draft_year)
    lines = [
        f"# Browser Collection Plan: {draft_year}",
        "",
        "Use this plan in a browser-enabled session.",
        "If the session has no network/browser capability, collect the files manually and then use stage commands.",
        "",
        "## Targets",
        f"- Draft HTML target: {paths.hockeydb_draft_html}",
        f"- Player pages dir: {paths.hockeydb_player_pages_dir}",
        f"- Elite Prospects CSV target: {paths.eliteprospects_csv}",
        "",
        "## Suggested Sources",
        f"- HockeyDB draft page (inferred pattern): https://www.hockeydb.com/ihdb/draft/nhl{draft_year}e.html",
        "- HockeyDB player pages: follow links from the draft page for featured players or the whole class",
        "- Elite Prospects: use your authenticated export flow for the same draft class",
        "",
        "## After Download",
        f"- Stage draft HTML: python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-draft-html --draft-year {draft_year} --source /path/to/nhl{draft_year}e.html",
        f"- Stage player pages: python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-player-pages --draft-year {draft_year} --source-dir /path/to/player_pages_dir",
        f"- Stage EP CSV: python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-eliteprospects-csv --draft-year {draft_year} --source /path/to/export.csv",
        f"- Or try auto-staging from Downloads: python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-downloads --draft-year {draft_year}",
    ]
    print("\n".join(lines))


def stage_downloads(draft_year: int, downloads_dir: Path) -> None:
    paths = demo_class_paths(REPO_ROOT, draft_year)
    if not downloads_dir.exists() or not downloads_dir.is_dir():
        raise FileNotFoundError(f"Downloads directory does not exist: {downloads_dir}")

    draft_candidates = ordered_matches(
        downloads_dir,
        [
            f"nhl{draft_year}e.html",
            f"*{draft_year}*draft*.html",
            f"*{draft_year}*.html",
        ],
    )
    ep_candidates = ordered_matches(
        downloads_dir,
        [
            f"*eliteprospects*{draft_year}*.csv",
            "*eliteprospects*.csv",
            f"*{draft_year}*.csv",
        ],
    )

    staged_any = False
    if draft_candidates:
        stage_file(draft_candidates[0], paths.hockeydb_draft_html)
        print(f"Staged draft HTML from Downloads: {draft_candidates[0]} -> {paths.hockeydb_draft_html}")
        staged_any = True
    else:
        print(f"No draft HTML candidate found in {downloads_dir}")

    if ep_candidates:
        stage_file(ep_candidates[0], paths.eliteprospects_csv)
        print(f"Staged Elite Prospects CSV from Downloads: {ep_candidates[0]} -> {paths.eliteprospects_csv}")
        staged_any = True
    else:
        print(f"No Elite Prospects CSV candidate found in {downloads_dir}")

    if not staged_any:
        print("Nothing staged automatically. Use the explicit stage-* commands if files live elsewhere or have unusual names.")


def ordered_matches(base_dir: Path, patterns: list[str]) -> list[Path]:
    matches: dict[Path, float] = {}
    for pattern in patterns:
        for path in base_dir.glob(pattern):
            if path.is_file():
                matches[path] = path.stat().st_mtime
    return [path for path, _ in sorted(matches.items(), key=lambda item: item[1], reverse=True)]


if __name__ == "__main__":
    main()
