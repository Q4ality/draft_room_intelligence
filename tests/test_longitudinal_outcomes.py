import csv
from datetime import date

import pytest

from draft_room_intelligence.cli import run_audit_outcome_labels
from draft_room_intelligence.reports.longitudinal_outcomes import (
    build_outcome_label_audit,
    eligible_outcome_labels,
    load_outcome_labels,
    write_outcome_label_audit,
)

HEADERS = [
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
]


def write_labels(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def row(player_id, draft_year, horizon_years, outcome_through):
    return {
        "player_id": player_id,
        "draft_year": str(draft_year),
        "horizon_years": str(horizon_years),
        "outcome_through": outcome_through,
        "nhl_games": "125",
        "nhl_points": "60",
        "nhl_toi_minutes": "2000",
        "goalie_starts": "0",
        "value_proxy": "1.5",
        "source": "nhl",
        "source_id": player_id,
        "source_url": "https://example.test/outcomes",
    }


def test_outcome_label_audit_distinguishes_mature_and_immature_labels(tmp_path):
    labels_path = tmp_path / "labels.csv"
    write_labels(
        labels_path,
        [
            row("p-2015", 2015, 7, "2022-06-30"),
            row("p-2021", 2021, 5, "2025-06-30"),
        ],
    )

    labels = load_outcome_labels(labels_path, as_of_date=date(2026, 8, 15))
    audit = build_outcome_label_audit(labels, labels_path, as_of_date=date(2026, 8, 15))

    assert audit.total_labels == 2
    assert audit.mature_labels == 1
    assert audit.immature_labels == 1
    assert [entry["status"] for entry in audit.rows] == ["mature", "immature"]
    assert [entry["eligible_for_model"] for entry in audit.rows] == ["yes", "no"]
    assert [label.player_id for label in eligible_outcome_labels(labels)] == ["p-2015"]


def test_outcome_label_audit_rejects_future_observation_and_duplicate_horizon(tmp_path):
    labels_path = tmp_path / "labels.csv"
    write_labels(
        labels_path,
        [
            row("p-future", 2019, 5, "2024-06-30"),
            row("p-future", 2019, 5, "2024-06-30"),
        ],
    )

    with pytest.raises(ValueError, match="duplicate outcome label"):
        load_outcome_labels(labels_path, as_of_date=date(2026, 8, 15))

    write_labels(labels_path, [row("p-future", 2019, 5, "2027-06-30")])
    with pytest.raises(ValueError, match="extends past audit date"):
        load_outcome_labels(labels_path, as_of_date=date(2026, 8, 15))

    write_labels(labels_path, [row("p-leakage", 2019, 3, "2026-06-30")])
    with pytest.raises(ValueError, match="extends beyond its 3-year target horizon"):
        load_outcome_labels(labels_path, as_of_date=date(2026, 8, 15))


def test_outcome_label_audit_rejects_non_finite_values_and_missing_provenance(tmp_path):
    labels_path = tmp_path / "labels.csv"
    invalid_value = row("p-nan", 2018, 5, "2023-06-30")
    invalid_value["nhl_toi_minutes"] = "NaN"
    write_labels(labels_path, [invalid_value])
    with pytest.raises(ValueError, match="invalid number nhl_toi_minutes"):
        load_outcome_labels(labels_path, as_of_date=date(2026, 8, 15))

    missing_url = row("p-source", 2018, 5, "2023-06-30")
    missing_url["source_url"] = ""
    write_labels(labels_path, [missing_url])
    with pytest.raises(ValueError, match="require source_url"):
        load_outcome_labels(labels_path, as_of_date=date(2026, 8, 15))


def test_write_outcome_label_audit_writes_status_and_summary(tmp_path):
    labels_path = tmp_path / "labels.csv"
    write_labels(labels_path, [row("p-2018", 2018, 5, "2023-06-30")])

    audit = write_outcome_label_audit(
        labels_path, tmp_path / "audit", as_of_date=date(2026, 8, 15)
    )

    assert audit.mature_labels == 1
    assert (tmp_path / "audit" / "label_status.csv").exists()
    assert "Mature labels: 1" in (tmp_path / "audit" / "summary.md").read_text(encoding="utf-8")


def test_run_audit_outcome_labels_prints_artifact_paths(capsys, tmp_path):
    labels_path = tmp_path / "labels.csv"
    write_labels(labels_path, [row("p-2018", 2018, 5, "2023-06-30")])

    run_audit_outcome_labels(labels_path, tmp_path / "audit", as_of_date=date(2026, 8, 15))

    output = capsys.readouterr().out
    assert "# Longitudinal outcome label audit:" in output
    assert "Mature labels: 1" in output
