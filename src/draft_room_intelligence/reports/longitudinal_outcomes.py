"""Audit time-bounded NHL outcome labels for retrospective value modeling."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REQUIRED_COLUMNS = (
    "player_id",
    "draft_year",
    "horizon_years",
    "outcome_through",
    "nhl_games",
    "nhl_points",
    "nhl_toi_minutes",
    "goalie_starts",
    "value_proxy",
    "source",
    "source_id",
    "source_url",
)
SUPPORTED_HORIZONS = (3, 5, 7)


@dataclass(frozen=True)
class OutcomeLabel:
    player_id: str
    draft_year: int
    horizon_years: int
    outcome_through: date
    nhl_games: int
    nhl_points: int
    nhl_toi_minutes: float
    goalie_starts: int
    value_proxy: float | None
    source: str
    source_id: str
    source_url: str

    @property
    def required_through(self) -> date:
        return date(self.draft_year + self.horizon_years, 6, 30)

    @property
    def is_mature(self) -> bool:
        return self.outcome_through == self.required_through


@dataclass(frozen=True)
class OutcomeLabelAudit:
    labels_path: Path
    as_of_date: date
    total_labels: int
    mature_labels: int
    immature_labels: int
    draft_years: tuple[int, ...]
    rows: list[dict[str, str]]


def load_outcome_labels(path: str | Path, *, as_of_date: date) -> list[OutcomeLabel]:
    labels_path = Path(path)
    with labels_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError(f"outcome labels missing required columns: {', '.join(missing)}")
        labels = [build_outcome_label(row, labels_path) for row in reader]

    seen: set[tuple[str, int]] = set()
    for label in labels:
        key = (label.player_id, label.horizon_years)
        if key in seen:
            raise ValueError(f"duplicate outcome label for player/horizon: {key[0]} / {key[1]}")
        seen.add(key)
        if label.outcome_through > as_of_date:
            raise ValueError(
                f"outcome label for {label.player_id} extends past audit date "
                f"{as_of_date.isoformat()}: {label.outcome_through.isoformat()}"
            )
        if label.outcome_through > label.required_through:
            raise ValueError(
                f"outcome label for {label.player_id} extends beyond its "
                f"{label.horizon_years}-year "
                f"target horizon: {label.outcome_through.isoformat()} > "
                f"{label.required_through.isoformat()}"
            )
    return labels


def eligible_outcome_labels(labels: list[OutcomeLabel]) -> list[OutcomeLabel]:
    """Return only labels that have reached their declared model target horizon."""

    return [label for label in labels if label.is_mature]


def build_outcome_label_audit(
    labels: list[OutcomeLabel], labels_path: str | Path, *, as_of_date: date
) -> OutcomeLabelAudit:
    rows: list[dict[str, str]] = []
    mature_labels = 0
    for label in sorted(
        labels, key=lambda item: (item.draft_year, item.player_id, item.horizon_years)
    ):
        mature = label.is_mature
        mature_labels += int(mature)
        rows.append(
            {
                "player_id": label.player_id,
                "draft_year": str(label.draft_year),
                "horizon_years": str(label.horizon_years),
                "outcome_through": label.outcome_through.isoformat(),
                "required_through": label.required_through.isoformat(),
                "status": "mature" if mature else "immature",
                "eligible_for_model": "yes" if mature else "no",
                "source": label.source,
                "source_id": label.source_id,
            }
        )
    return OutcomeLabelAudit(
        labels_path=Path(labels_path),
        as_of_date=as_of_date,
        total_labels=len(labels),
        mature_labels=mature_labels,
        immature_labels=len(labels) - mature_labels,
        draft_years=tuple(sorted({label.draft_year for label in labels})),
        rows=rows,
    )


def write_outcome_label_audit(
    labels_path: str | Path, output_dir: str | Path, *, as_of_date: date
) -> OutcomeLabelAudit:
    labels = load_outcome_labels(labels_path, as_of_date=as_of_date)
    audit = build_outcome_label_audit(labels, labels_path, as_of_date=as_of_date)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "label_status.csv").open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(audit.rows[0]) if audit.rows else ["player_id"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit.rows)
    (root / "summary.md").write_text(format_outcome_label_audit(audit), encoding="utf-8")
    return audit


def format_outcome_label_audit(audit: OutcomeLabelAudit) -> str:
    years = ", ".join(str(year) for year in audit.draft_years) or "none"
    return "\n".join(
        [
            "# Longitudinal Outcome Label Audit",
            "",
            f"- Labels: {audit.total_labels}",
            f"- Mature labels: {audit.mature_labels}",
            f"- Immature labels: {audit.immature_labels}",
            f"- Draft years: {years}",
            f"- Audit date: {audit.as_of_date.isoformat()}",
            "",
            (
                "A label is mature only when its `outcome_through` date exactly matches the "
                "end of its declared draft horizon."
            ),
            (
                "Immature labels are retained for coverage planning but must not be used as "
                "final retrospective targets."
            ),
            "",
        ]
    )


def build_outcome_label(row: dict[str, str], path: Path) -> OutcomeLabel:
    player_id = required_text(row, "player_id", path)
    draft_year = required_int(row, "draft_year", path)
    horizon_years = required_int(row, "horizon_years", path)
    if horizon_years not in SUPPORTED_HORIZONS:
        raise ValueError(f"unsupported outcome horizon for {player_id}: {horizon_years}")
    return OutcomeLabel(
        player_id=player_id,
        draft_year=draft_year,
        horizon_years=horizon_years,
        outcome_through=required_date(row, "outcome_through", path),
        nhl_games=required_non_negative_int(row, "nhl_games", player_id),
        nhl_points=required_non_negative_int(row, "nhl_points", player_id),
        nhl_toi_minutes=required_non_negative_float(row, "nhl_toi_minutes", player_id),
        goalie_starts=required_non_negative_int(row, "goalie_starts", player_id),
        value_proxy=optional_float(row.get("value_proxy", ""), player_id, "value_proxy"),
        source=required_text(row, "source", path),
        source_id=required_text(row, "source_id", path),
        source_url=required_text(row, "source_url", path),
    )


def required_text(row: dict[str, str], field: str, path: Path) -> str:
    value = row.get(field, "").strip()
    if not value:
        raise ValueError(f"outcome labels require {field}: {path}")
    return value


def required_int(row: dict[str, str], field: str, path: Path) -> int:
    value = required_text(row, field, path)
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"outcome labels require integer {field}: {value}") from error


def required_date(row: dict[str, str], field: str, path: Path) -> date:
    value = required_text(row, field, path)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"outcome labels require ISO date {field}: {value}") from error


def required_non_negative_int(row: dict[str, str], field: str, player_id: str) -> int:
    try:
        value = int(row.get(field, ""))
    except ValueError as error:
        raise ValueError(f"outcome label {player_id} has invalid integer {field}") from error
    if value < 0:
        raise ValueError(f"outcome label {player_id} has negative {field}")
    return value


def required_non_negative_float(row: dict[str, str], field: str, player_id: str) -> float:
    try:
        value = float(row.get(field, ""))
    except ValueError as error:
        raise ValueError(f"outcome label {player_id} has invalid number {field}") from error
    if not math.isfinite(value):
        raise ValueError(f"outcome label {player_id} has invalid number {field}")
    if value < 0:
        raise ValueError(f"outcome label {player_id} has negative {field}")
    return value


def optional_float(value: str, player_id: str, field: str) -> float | None:
    if not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"outcome label {player_id} has invalid number {field}") from error
    if not math.isfinite(parsed):
        raise ValueError(f"outcome label {player_id} has invalid number {field}")
    return parsed
