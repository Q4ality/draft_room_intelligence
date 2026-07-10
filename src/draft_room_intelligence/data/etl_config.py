"""Configuration helpers for draft-year ETL paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DraftYearETLConfig:
    draft_year: int
    output_root: Path
    base_dir: Path | None = None
    hockeydb_draft_html: Path | None = None
    hockeydb_player_pages_dir: Path | None = None
    eliteprospects_csv: Path | None = None
    match_map: Path | None = None
    match_template_output: Path | None = None
    timing: str = "pre_draft"
    replace_timing: str = "pre_draft"
    candidate_count: int = 3

    @property
    def base_output_dir(self) -> Path:
        return self.output_root / "base"

    @property
    def eliteprospects_output_dir(self) -> Path:
        return self.output_root / "eliteprospects"

    @property
    def final_output_dir(self) -> Path:
        return self.output_root / "final"

    def resolve_match_template_output(self) -> Path | None:
        return self.match_template_output
