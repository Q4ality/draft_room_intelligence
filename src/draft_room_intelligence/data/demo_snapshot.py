"""Versioned, self-contained input bundles for reproducible demo builds."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_MANIFEST = "snapshot.json"
REQUIRED_FINAL_FILES = (
    "players.csv",
    "draft_selections.csv",
    "rankings.csv",
    "season_stat_lines.csv",
)


@dataclass(frozen=True)
class DemoSnapshot:
    root: Path
    draft_year: int
    data_dir: Path
    advanced_stats_csv: Path | None
    team_depth_csv: Path | None
    snapshot_id: str


def create_demo_snapshot(
    data_dir: str | Path,
    snapshot_dir: str | Path,
    *,
    draft_year: int,
    team_depth_csv: str | Path | None = None,
    advanced_stats_csv: str | Path | None = None,
) -> DemoSnapshot:
    source = Path(data_dir)
    target = Path(snapshot_dir)
    if not source.is_dir():
        raise ValueError(f"Demo dataset directory is missing: {source}")
    validate_final_dataset(source)
    if target.exists():
        raise ValueError(f"Snapshot directory already exists: {target}")

    target.mkdir(parents=True)
    final_dir = target / "final"
    shutil.copytree(source, final_dir)
    source_advanced = (
        Path(advanced_stats_csv) if advanced_stats_csv else source / "advanced_stat_lines.csv"
    )
    if advanced_stats_csv and source_advanced.is_file():
        shutil.copy2(source_advanced, target / "advanced_stat_lines.csv")
        advanced_path = target / "advanced_stat_lines.csv"
    elif (final_dir / "advanced_stat_lines.csv").is_file():
        advanced_path = final_dir / "advanced_stat_lines.csv"
    else:
        advanced_path = None

    source_depth = Path(team_depth_csv) if team_depth_csv else None
    if source_depth is not None:
        if not source_depth.is_file():
            raise ValueError(f"Team-depth CSV is missing: {source_depth}")
        shutil.copy2(source_depth, target / "team_depth.csv")
        depth_path = target / "team_depth.csv"
    else:
        depth_path = None

    entries = fingerprint_files(target)
    snapshot_id = hash_entries(entries)
    manifest = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": f"sha256:{snapshot_id}",
        "draft_year": draft_year,
        "data_dir": "final",
        "advanced_stats_csv": relative_or_none(advanced_path, target),
        "team_depth_csv": relative_or_none(depth_path, target),
        "files": entries,
    }
    (target / SNAPSHOT_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return DemoSnapshot(
        target,
        draft_year,
        final_dir,
        advanced_path,
        depth_path,
        manifest["snapshot_id"],
    )


def load_demo_snapshot(snapshot_dir: str | Path) -> DemoSnapshot:
    root = Path(snapshot_dir)
    manifest_path = root / SNAPSHOT_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"Demo snapshot manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Unsupported demo snapshot schema version")
    entries = manifest.get("files")
    snapshot_id = str(manifest.get("snapshot_id", "")).removeprefix("sha256:")
    if not isinstance(entries, list) or hash_entries(entries) != snapshot_id:
        raise ValueError("Demo snapshot manifest has an invalid snapshot ID")
    actual_entries = fingerprint_files(root)
    if actual_entries != entries:
        raise ValueError("Demo snapshot files do not match the manifest checksums")

    data_dir = root / str(manifest.get("data_dir", "final"))
    validate_final_dataset(data_dir)
    advanced = optional_snapshot_path(root, manifest.get("advanced_stats_csv"))
    depth = optional_snapshot_path(root, manifest.get("team_depth_csv"))
    draft_year = manifest.get("draft_year")
    if not isinstance(draft_year, int):
        raise ValueError("Demo snapshot draft year is invalid")
    return DemoSnapshot(root, draft_year, data_dir, advanced, depth, str(manifest["snapshot_id"]))


def validate_final_dataset(data_dir: Path) -> None:
    missing = [name for name in REQUIRED_FINAL_FILES if not (data_dir / name).is_file()]
    if missing:
        raise ValueError(f"Demo dataset is missing required files: {', '.join(missing)}")


def fingerprint_files(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != SNAPSHOT_MANIFEST
    ]


def hash_entries(entries: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    digest.update(f"demo-snapshot-v{SNAPSHOT_SCHEMA_VERSION}\n".encode())
    for entry in entries:
        digest.update(f"{entry['path']}\0{entry['sha256']}\0{entry['bytes']}\n".encode())
    return digest.hexdigest()


def relative_or_none(path: Path | None, root: Path) -> str | None:
    return path.relative_to(root).as_posix() if path is not None else None


def optional_snapshot_path(root: Path, value: object) -> Path | None:
    if value in (None, ""):
        return None
    path = root / str(value)
    if not path.is_file():
        raise ValueError(f"Demo snapshot supporting file is missing: {path}")
    return path
