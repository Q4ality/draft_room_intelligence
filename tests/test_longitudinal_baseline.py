import csv
from datetime import date

from draft_room_intelligence.evaluation.metrics import precision_at_n
from draft_room_intelligence.reports.longitudinal_baseline import (
    build_longitudinal_baseline_report,
    write_longitudinal_baseline_report,
)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def label_row(player_id, draft_year, games, points, starts=0):
    return {
        "player_id": player_id,
        "draft_year": str(draft_year),
        "horizon_years": "5",
        "outcome_through": f"{draft_year + 5}-06-30",
        "nhl_games": str(games),
        "nhl_points": str(points),
        "nhl_toi_minutes": "100.0",
        "goalie_starts": str(starts),
        "value_proxy": "",
        "source": "test",
        "source_id": player_id,
        "source_url": f"https://example.test/{player_id}",
    }


def write_class(root, year, rows):
    class_dir = root / str(year) / "final"
    write_csv(
        class_dir / "draft_selections.csv",
        ["player_id", "overall_pick"],
        [{"player_id": row["player_id"], "overall_pick": row["pick"]} for row in rows],
    )
    write_csv(
        class_dir / "players.csv",
        ["player_id", "position"],
        [{"player_id": row["player_id"], "position": row["position"]} for row in rows],
    )


def test_longitudinal_baseline_uses_temporal_split_and_writes_reports(tmp_path):
    labels_root = tmp_path / "labels"
    class_root = tmp_path / "classes"
    classes = {
        2014: [
            {
                "player_id": "p14-first",
                "pick": "1",
                "position": "C/RW",
                "games": 200,
                "points": 100,
            },
            {"player_id": "p14-late", "pick": "100", "position": "D", "games": 0, "points": 0},
        ],
        2015: [
            {
                "player_id": "p15-goalie",
                "pick": "20",
                "position": "G",
                "games": 110,
                "points": 0,
                "starts": 50,
            },
            {"player_id": "p15-late", "pick": "120", "position": "LW", "games": 5, "points": 1},
        ],
        2019: [
            {"player_id": "p19-first", "pick": "2", "position": "C", "games": 150, "points": 60},
            {"player_id": "p19-late", "pick": "150", "position": "D", "games": 0, "points": 0},
        ],
    }
    fields = list(label_row("p", 2014, 0, 0))
    for year, rows in classes.items():
        write_class(class_root, year, rows)
        write_csv(
            labels_root / str(year) / "5y.csv",
            fields,
            [
                label_row(
                    row["player_id"],
                    year,
                    row["games"],
                    row["points"],
                    row.get("starts", 0),
                )
                for row in rows
            ],
        )

    report = build_longitudinal_baseline_report(
        labels_root,
        class_root,
        as_of_date=date(2026, 8, 22),
        train_end_year=2015,
        test_start_year=2019,
    )
    assert report.train_count == 4
    assert report.test_count == 2
    assert {row["draft_year"] for row in report.rows} == {"2019"}
    assert all(0.0 <= float(row["regular_prediction"]) <= 1.0 for row in report.rows)
    assert all(0.0 <= float(row["impact_prediction"]) <= 1.0 for row in report.rows)
    assert report.summary["as_of_date"] == "2026-08-22"
    assert report.summary["train_draft_years"] == "2014,2015"
    assert report.summary["test_draft_years"] == "2019"
    assert report.summary["slot_score_max_pick"] == "120"
    expected_regular_precision = precision_at_n(
        [row["regular_nhl"] == "1" for row in report.rows],
        [float(row["regular_prediction"]) for row in report.rows],
        25,
    )
    expected_impact_precision = precision_at_n(
        [row["impact_nhl"] == "1" for row in report.rows],
        [float(row["impact_prediction"]) for row in report.rows],
        25,
    )
    assert report.summary["regular_nhl_precision_at_25"] == f"{expected_regular_precision:.4f}"
    assert report.summary["impact_nhl_precision_at_25"] == f"{expected_impact_precision:.4f}"

    write_longitudinal_baseline_report(
        labels_root,
        class_root,
        tmp_path / "report",
        as_of_date=date(2026, 8, 22),
        train_end_year=2015,
        test_start_year=2019,
    )
    assert (tmp_path / "report" / "predictions.csv").exists()
    assert (tmp_path / "report" / "model_coefficients.csv").exists()
    assert "Slot-and-Role" in (tmp_path / "report" / "summary.md").read_text(encoding="utf-8")
