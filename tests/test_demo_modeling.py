import csv
import json

from draft_room_intelligence.cli import run_report_demo_modeling
from draft_room_intelligence.reports.demo_modeling import build_demo_modeling_report


def write_demo_package(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"draft_year": 2025, "player_count": 4, "dataset_status": "strong"}),
        encoding="utf-8",
    )
    rows = [
        board_row("p1", "Consensus Anchor", "forward", 1, 1, "aligned", "high", "OHL"),
        board_row("p2", "Model Mover", "forward", 10, 30, "model_higher", "medium", "USHL"),
        board_row("p3", "Consensus Mover", "defense", 35, 12, "consensus_higher", "high", "WHL"),
        board_row("p4", "Low Evidence Mover", "goalie", 20, 45, "model_higher", "low", "MHL", position="G"),
    ]
    with (tmp_path / "board.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def board_row(
    player_id,
    name,
    role_group,
    board_rank,
    consensus_rank,
    disagreement_bucket,
    evidence_depth,
    primary_league,
    *,
    position="C",
):
    return {
        "player_id": player_id,
        "draft_year": "2025",
        "board_rank": str(board_rank),
        "name": name,
        "position": position,
        "role_group": role_group,
        "nationality": "CAN",
        "age_at_draft": "18.0",
        "height_cm": "180",
        "weight_kg": "80",
        "handedness": "L",
        "primary_league": primary_league,
        "primary_league_family": "Test",
        "primary_competition_level": "junior",
        "consensus_rank": str(consensus_rank),
        "model_score": "0.6",
        "board_score": "0.6",
        "adjusted_production_score": "0.4",
        "adjusted_ppg": "0.8",
        "role_rank": "1",
        "role_percentile": "0.8",
        "adult_game_share": "0",
        "junior_game_share": "1",
        "college_game_share": "0",
        "pro_game_share": "0",
        "playoff_game_share": "0",
        "average_league_weight": "0.9",
        "pre_draft_row_count": "2",
        "pre_draft_league_count": "1",
        "goalie_save_percentage": "0",
        "goalie_goals_against_average": "0",
        "goalie_quality_score": "0",
        "evidence_depth": evidence_depth,
        "consensus_delta": str(board_rank - consensus_rank),
        "disagreement_bucket": disagreement_bucket,
        "badges": "",
        "short_reason": "test reason",
        "risk_note": "test risk",
    }


def test_build_demo_modeling_report_summarizes_consensus_movement(tmp_path):
    write_demo_package(tmp_path)

    report = build_demo_modeling_report(tmp_path, top_n=3)

    assert report.moved_10_plus == 3
    assert report.high_or_medium_moved_10_plus == 2
    assert report.top_n_overlap["top_10"] == 1
    assert report.movement_rows[0]["name"] == "Low Evidence Mover"
    assert {role.role_group for role in report.role_movements} == {"defense", "forward", "goalie"}


def test_run_report_demo_modeling_writes_csv_and_summary(capsys, tmp_path):
    demo_dir = tmp_path / "demo"
    output_dir = tmp_path / "modeling"
    demo_dir.mkdir()
    write_demo_package(demo_dir)

    run_report_demo_modeling(demo_dir, output_dir, top_n=2)

    output = capsys.readouterr().out
    assert "# Demo modeling sanity report:" in output
    assert (output_dir / "largest_movements.csv").exists()
    assert (output_dir / "summary.md").exists()
    assert "Players moved 10+ slots" in (output_dir / "summary.md").read_text(encoding="utf-8")
