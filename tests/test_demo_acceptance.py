import csv
import json

from draft_room_intelligence.reports.demo_acceptance import write_demo_acceptance_report
from draft_room_intelligence.reports.demo_baseline import artifact_metrics


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def board_row(player_id, name, rank, consensus, role="forward", evidence="high"):
    return {
        "player_id": player_id,
        "board_rank": str(rank),
        "name": name,
        "position": "D" if role == "defense" else "C",
        "role_group": role,
        "consensus_rank": str(consensus),
        "evidence_depth": evidence,
    }


def write_brief_artifacts(demo):
    (demo / "meeting_brief.html").write_text(
        "<h1>2025 Guided Draft Meeting Brief</h1>", encoding="utf-8"
    )
    (demo / "meeting_brief.pdf").write_bytes(b"%PDF-1.4\n" + (b"0" * 1_100))


def write_baseline_artifacts(demo, rows, details):
    metrics = {
        "draft_year": 2025,
        "player_count": len(rows),
        "season_stat_line_count": 0,
        **artifact_metrics(rows, details),
    }
    baseline = {
        "schema_version": 1,
        "baseline_id": "sha256:test",
        "dataset_fingerprint": "test",
        "source_files": [],
        "metrics": metrics,
    }
    (demo / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    (demo / "manifest.json").write_text(
        json.dumps(
            {
                "baseline_id": baseline["baseline_id"],
                "baseline_metrics": metrics,
            }
        ),
        encoding="utf-8",
    )


def test_write_demo_acceptance_report_passes_current_demo_shape(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    rows = [
        board_row("p1", "Porter Martone", 1, 3),
        board_row("p2", "Michael Misa", 2, 2),
        board_row("p3", "Matthew Schaefer", 3, 1, role="defense"),
        board_row("p4", "Pyotr Andreyanov", 27, 20, role="goalie"),
    ]
    rows.extend(board_row(f"x{i}", f"Player {i}", i, i, evidence="medium") for i in range(5, 225))
    write_rows(demo / "board.csv", rows)
    details = []
    for row in rows:
        detail = {
            "player_id": row["player_id"],
            "header": {"name": row["name"]},
            "stat_evidence": {},
            "team_fit_options": [],
        }
        if row["name"] == "Michael Misa":
            detail["team_fit_options"] = [
                {
                    "team_id": "SJS",
                    "role_type": "scoring_center",
                    "score": 0.55,
                    "pipeline_need_score": 0.25,
                }
            ]
        if row["name"] == "Matthew Schaefer":
            detail["team_fit_options"] = [
                {"team_id": "NYI", "role_type": "two_way_defense", "score": 0.55},
                {"team_id": "CHI", "role_type": "two_way_defense", "score": 0.40},
            ]
        details.append(detail)
    (demo / "players.json").write_text(json.dumps(details), encoding="utf-8")
    write_baseline_artifacts(demo, rows, details)
    (demo / "index.html").write_text(
        "<th>Production</th><section>Prospect Stats Evidence</section>"
        "<button>Start Guided Demo</button><button id='guided-previous'></button>"
        "<button id='guided-next'></button>",
        encoding="utf-8",
    )
    write_brief_artifacts(demo)

    report = write_demo_acceptance_report(demo, tmp_path / "acceptance")

    assert report.passed
    assert report.failed_count == 0
    assert (tmp_path / "acceptance" / "summary.md").exists()


def test_write_demo_acceptance_report_fails_when_schaefer_drops(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    rows = [
        board_row("p1", "Porter Martone", 1, 3),
        board_row("p2", "Michael Misa", 2, 2),
        board_row("p3", "Matthew Schaefer", 18, 1, role="defense"),
        board_row("p4", "Pyotr Andreyanov", 27, 20, role="goalie"),
    ]
    rows.extend(board_row(f"x{i}", f"Player {i}", i, i, evidence="medium") for i in range(5, 225))
    write_rows(demo / "board.csv", rows)
    details = [{"player_id": row["player_id"], "stat_evidence": {}} for row in rows]
    (demo / "players.json").write_text(json.dumps(details), encoding="utf-8")
    write_baseline_artifacts(demo, rows, details)
    (demo / "index.html").write_text(
        "<th>Production</th><section>Prospect Stats Evidence</section>"
        "<button>Start Guided Demo</button><button id='guided-previous'></button>"
        "<button id='guided-next'></button>",
        encoding="utf-8",
    )
    write_brief_artifacts(demo)

    report = write_demo_acceptance_report(demo, tmp_path / "acceptance")

    assert not report.passed
    failed = [check for check in report.checks if check.status == "fail"]
    assert any(check.check_id == "matthew_schaefer_rank" for check in failed)


def test_demo_acceptance_fails_when_board_drifts_from_baseline(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    rows = [board_row("p1", "Player One", 1, 1)]
    details = [{"player_id": "p1", "stat_evidence": {}}]
    write_rows(demo / "board.csv", rows)
    (demo / "players.json").write_text(json.dumps(details), encoding="utf-8")
    write_baseline_artifacts(demo, rows, details)
    rows[0]["evidence_depth"] = "low"
    write_rows(demo / "board.csv", rows)
    (demo / "index.html").write_text("", encoding="utf-8")
    write_brief_artifacts(demo)

    report = write_demo_acceptance_report(demo, tmp_path / "acceptance")

    failed = {check.check_id for check in report.checks if check.status == "fail"}
    assert "baseline_board_metrics" in failed
