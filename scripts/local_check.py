"""Run offline-safe validation, baseline review, and lineage audit."""

from __future__ import annotations

import csv
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
BASELINE_DIR = ROOT / "outputs" / "longitudinal_slot_role_baseline"
LINEAGE_DIR = ROOT / "outputs" / "ingestion_lineage"
REVIEW_PATH = ROOT / "outputs" / "local_review" / "summary.md"


def run(*args: str) -> None:
    subprocess.run([PYTHON, *args], cwd=ROOT, check=True)


def first_row(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.DictReader(handle), {})


def main() -> None:
    run("-m", "pytest", "-q")
    run(
        "-m",
        "draft_room_intelligence.cli",
        "report-longitudinal-baseline",
        "data/processed/outcome_labels",
        "data/processed/draft_classes",
        str(BASELINE_DIR),
        "--as-of-date",
        "2026-08-25",
    )
    baseline = first_row(BASELINE_DIR / "summary.csv")
    if baseline.get("train_players") != "1064" or baseline.get("test_players") != "656":
        raise RuntimeError("unexpected longitudinal baseline inputs")
    run(
        "-m",
        "draft_room_intelligence.cli",
        "report-ingestion-plan",
        "data/reference/ingestion_source_families.csv",
        str(LINEAGE_DIR),
        "--project-root",
        ".",
    )
    with (LINEAGE_DIR / "source_family_audit.csv").open(newline="", encoding="utf-8") as handle:
        lineage = Counter(row["readiness"] for row in csv.DictReader(handle))
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text(
        "\n".join(
            [
                "# Local Validation and Baseline Review",
                "",
                "## Validation",
                "",
                "- Test suite: passed.",
                "- Longitudinal audit date: " + baseline["as_of_date"] + ".",
                "- Training / held-out players: "
                + baseline["train_players"]
                + " / "
                + baseline["test_players"]
                + ".",
                "",
                "## Held-out Baseline",
                "",
                "- Regular-NHL Brier: " + baseline["regular_nhl_brier"] + ".",
                "- Impact-player Brier: " + baseline["impact_nhl_brier"] + ".",
                "- Regular-NHL Precision@25: " + baseline["regular_nhl_precision_at_25"] + ".",
                "- Impact-player Precision@25: " + baseline["impact_nhl_precision_at_25"] + ".",
                "",
                (
            "Decision: use this as an audited benchmark and decision-support input; "
            "do not claim it outperforms consensus until comparative held-out evaluation is added."
        ),
                "",
                "## Ingestion Lineage",
                "",
                "- Ready: " + str(lineage["ready"]),
                "- Partial: " + str(lineage["partial"]),
                "- Blocked: " + str(lineage["blocked"]),
                "",
                (
            "The workflow is offline-safe: it records cache, normalized-output, documentation, "
            "and test readiness without downloading or overwriting provider data. Refresh source "
            "data only through an approved, credentialed collection command."
        ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("Local review: " + str(REVIEW_PATH))


if __name__ == "__main__":
    main()
