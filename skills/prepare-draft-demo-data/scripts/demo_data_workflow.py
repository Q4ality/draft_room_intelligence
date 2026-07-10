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
from draft_room_intelligence.cli import run_build_demo_site
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
        run_build_demo_site(paths.processed_demo_dir / "final", paths.outputs_dir)


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


if __name__ == "__main__":
    main()
