"""Canonical dataset identity and metrics for a generated demo package."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from draft_room_intelligence.domain import HistoricalProspect

BASELINE_SCHEMA_VERSION = 1
NORMALIZED_BASELINE_FILES = (
    "players.csv",
    "draft_selections.csv",
    "nhl_outcomes.csv",
    "rankings.csv",
    "season_stat_lines.csv",
    "advanced_stat_lines.csv",
    "ep_pdf_profiles.csv",
    "ep_pdf_tool_grades.csv",
)


def build_demo_baseline(
    data_path: str | Path,
    prospects: list[HistoricalProspect],
    board_rows: list[dict[str, str]],
    player_details: list[dict[str, object]],
    *,
    supporting_paths: Iterable[str | Path] = (),
) -> dict[str, object]:
    source_files = fingerprint_source_files(data_path, supporting_paths=supporting_paths)
    dataset_fingerprint = hash_source_files(source_files)
    evidence_counts = Counter(row.get("evidence_depth", "") for row in board_rows)
    evidence_counts.pop("", None)
    deltas = [
        abs(integer(row.get("board_rank")) - integer(row.get("consensus_rank")))
        for row in board_rows
    ]
    metrics = {
        "draft_year": prospects[0].draft_year if prospects else None,
        "player_count": len(prospects),
        "season_stat_line_count": sum(
            len(prospect.pre_draft_stat_lines) for prospect in prospects
        ),
        "board_row_count": len(board_rows),
        "player_detail_count": len(player_details),
        "evidence_depth_counts": dict(sorted(evidence_counts.items())),
        "top_50_consensus_overlap": top_n_overlap(board_rows, 50),
        "average_absolute_consensus_delta": round(
            sum(deltas) / len(deltas) if deltas else 0.0,
            6,
        ),
    }
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "baseline_id": f"sha256:{dataset_fingerprint}",
        "dataset_fingerprint": dataset_fingerprint,
        "source_files": source_files,
        "metrics": metrics,
    }


def write_demo_baseline(output_dir: str | Path, baseline: dict[str, object]) -> Path:
    path = Path(output_dir) / "baseline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_demo_baseline(demo_output_dir: str | Path) -> dict[str, object]:
    path = Path(demo_output_dir) / "baseline.json"
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fingerprint_source_files(
    data_path: str | Path,
    *,
    supporting_paths: Iterable[str | Path] = (),
) -> list[dict[str, object]]:
    root = Path(data_path)
    entries: list[tuple[str, Path]] = []
    if root.is_dir():
        entries.extend(
            (name, root / name)
            for name in NORMALIZED_BASELINE_FILES
            if (root / name).is_file()
        )
    elif root.is_file():
        entries.append((root.name, root))
    included_paths = {path.resolve() for _, path in entries}
    support_index = 0
    for value in supporting_paths:
        path = Path(value)
        if path.is_file() and path.resolve() not in included_paths:
            support_index += 1
            entries.append((f"support/{support_index}/{path.name}", path))
            included_paths.add(path.resolve())
    return [
        {
            "path": label,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for label, path in sorted(entries)
    ]


def hash_source_files(source_files: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    digest.update(f"demo-baseline-v{BASELINE_SCHEMA_VERSION}\n".encode())
    for row in source_files:
        digest.update(f"{row['path']}\0{row['sha256']}\0{row['bytes']}\n".encode())
    return digest.hexdigest()


def artifact_metrics(
    board_rows: list[dict[str, str]],
    player_details: list[dict[str, object]],
) -> dict[str, object]:
    evidence_counts = Counter(row.get("evidence_depth", "") for row in board_rows)
    evidence_counts.pop("", None)
    deltas = [
        abs(integer(row.get("board_rank")) - integer(row.get("consensus_rank")))
        for row in board_rows
    ]
    return {
        "board_row_count": len(board_rows),
        "player_detail_count": len(player_details),
        "evidence_depth_counts": dict(sorted(evidence_counts.items())),
        "top_50_consensus_overlap": top_n_overlap(board_rows, 50),
        "average_absolute_consensus_delta": round(
            sum(deltas) / len(deltas) if deltas else 0.0,
            6,
        ),
    }


def read_board(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def top_n_overlap(rows: list[dict[str, str]], n: int) -> int:
    board_ids = {
        row.get("player_id", "")
        for row in rows
        if 0 < integer(row.get("board_rank")) <= n
    }
    consensus_ids = {
        row.get("player_id", "")
        for row in rows
        if 0 < integer(row.get("consensus_rank")) <= n
    }
    return len(board_ids & consensus_ids)


def integer(value: object) -> int:
    try:
        return int(float(str(value or 0)))
    except ValueError:
        return 0
