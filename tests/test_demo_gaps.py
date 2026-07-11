import csv
import json

from draft_room_intelligence.cli import run_report_demo_gaps
from draft_room_intelligence.reports.demo_gaps import build_demo_gap_report


def write_demo_package(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "draft_year": 2025,
                "player_count": 3,
                "dataset_status": "strong",
            }
        ),
        encoding="utf-8",
    )
    rows = [
        {
            "player_id": "p1",
            "draft_year": "2025",
            "board_rank": "12",
            "name": "Trusted Player",
            "position": "C",
            "role_group": "forward",
            "nationality": "CAN",
            "age_at_draft": "18.1",
            "height_cm": "180",
            "weight_kg": "80",
            "handedness": "L",
            "primary_league": "OHL",
            "primary_league_family": "CHL",
            "primary_competition_level": "junior",
            "consensus_rank": "10",
            "model_score": "0.7",
            "board_score": "0.7",
            "adjusted_production_score": "0.5",
            "adjusted_ppg": "1.0",
            "role_rank": "1",
            "role_percentile": "0.9",
            "adult_game_share": "0",
            "junior_game_share": "1",
            "college_game_share": "0",
            "pro_game_share": "0",
            "playoff_game_share": "0.1",
            "average_league_weight": "1",
            "pre_draft_row_count": "3",
            "pre_draft_league_count": "1",
            "goalie_save_percentage": "0",
            "goalie_goals_against_average": "0",
            "goalie_quality_score": "0",
            "evidence_depth": "high",
            "consensus_delta": "2",
            "disagreement_bucket": "aligned",
            "badges": "",
            "short_reason": "",
            "risk_note": "",
        },
        {
            "player_id": "p2",
            "draft_year": "2025",
            "board_rank": "40",
            "name": "USHL Gap",
            "position": "C",
            "role_group": "forward",
            "nationality": "USA",
            "age_at_draft": "18.2",
            "height_cm": "178",
            "weight_kg": "76",
            "handedness": "R",
            "primary_league": "USHL",
            "primary_league_family": "USHL",
            "primary_competition_level": "junior",
            "consensus_rank": "55",
            "model_score": "0.6",
            "board_score": "0.6",
            "adjusted_production_score": "0.4",
            "adjusted_ppg": "0.8",
            "role_rank": "8",
            "role_percentile": "0.7",
            "adult_game_share": "0",
            "junior_game_share": "1",
            "college_game_share": "0",
            "pro_game_share": "0",
            "playoff_game_share": "0",
            "average_league_weight": "0.9",
            "pre_draft_row_count": "1",
            "pre_draft_league_count": "1",
            "goalie_save_percentage": "0",
            "goalie_goals_against_average": "0",
            "goalie_quality_score": "0",
            "evidence_depth": "low",
            "consensus_delta": "-15",
            "disagreement_bucket": "model_higher",
            "badges": "Model Higher",
            "short_reason": "",
            "risk_note": "",
        },
        {
            "player_id": "p3",
            "draft_year": "2025",
            "board_rank": "90",
            "name": "MHL Goalie Gap",
            "position": "G",
            "role_group": "goalie",
            "nationality": "RUS",
            "age_at_draft": "18.0",
            "height_cm": "185",
            "weight_kg": "82",
            "handedness": "L",
            "primary_league": "MHL",
            "primary_league_family": "Russia Junior",
            "primary_competition_level": "junior",
            "consensus_rank": "80",
            "model_score": "0.5",
            "board_score": "0.5",
            "adjusted_production_score": "0",
            "adjusted_ppg": "0",
            "role_rank": "0",
            "role_percentile": "0",
            "adult_game_share": "0",
            "junior_game_share": "1",
            "college_game_share": "0",
            "pro_game_share": "0",
            "playoff_game_share": "0",
            "average_league_weight": "0.8",
            "pre_draft_row_count": "1",
            "pre_draft_league_count": "1",
            "goalie_save_percentage": "0.91",
            "goalie_goals_against_average": "2.5",
            "goalie_quality_score": "0.5",
            "evidence_depth": "low",
            "consensus_delta": "10",
            "disagreement_bucket": "aligned",
            "badges": "",
            "short_reason": "",
            "risk_note": "",
        },
    ]
    with (tmp_path / "board.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_build_demo_gap_report_prioritizes_low_evidence_players(tmp_path):
    write_demo_package(tmp_path)

    report = build_demo_gap_report(tmp_path, top_n=2)

    assert len(report.low_evidence_rows) == 2
    assert len(report.priority_rows) == 2
    assert report.priority_rows[0]["name"] == "USHL Gap"
    assert report.priority_rows[0]["suggested_source_strategy"] == "NCAA/USHL/USNTDP"
    assert report.priority_rows[1]["suggested_source_strategy"] == "Russian goalie stats"


def test_run_report_demo_gaps_writes_csv_and_summary(capsys, tmp_path):
    demo_dir = tmp_path / "demo"
    output_dir = tmp_path / "gaps"
    demo_dir.mkdir()
    write_demo_package(demo_dir)

    run_report_demo_gaps(demo_dir, output_dir, top_n=1)

    output = capsys.readouterr().out
    assert "# Demo data gap report:" in output
    assert (output_dir / "priority_gaps.csv").exists()
    assert (output_dir / "summary.md").exists()
    assert "USHL Gap" in (output_dir / "summary.md").read_text(encoding="utf-8")
