import csv
import json

from draft_room_intelligence.reports.demo_sanity import write_demo_sanity_report


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_write_demo_sanity_report_outputs_role_and_story_checks(tmp_path):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    write_rows(
        demo_dir / "board.csv",
        [
            {
                "player_id": "p1",
                "board_rank": "1",
                "name": "Matthew Schaefer",
                "position": "D",
                "role_group": "defense",
                "consensus_rank": "1",
                "model_score": "0.72",
                "board_score": "1.0",
                "team_adjusted_score": "0.95",
                "ep_tool_score": "0.80",
                "team_fit_score": "0.67",
                "short_reason": "EP evidence",
            },
            {
                "player_id": "g1",
                "board_rank": "2",
                "name": "Alexei Medvedev",
                "position": "G",
                "role_group": "goalie",
                "consensus_rank": "47",
                "model_score": "0.70",
                "board_score": "0.88",
                "team_adjusted_score": "0.83",
                "ep_tool_score": "0.60",
                "team_fit_score": "0.40",
                "short_reason": "Goalie signal",
            },
        ],
    )
    (demo_dir / "players.json").write_text(
        json.dumps(
            [
                {
                    "header": {"name": "Matthew Schaefer"},
                    "stat_evidence": {
                        "role_group": "defense",
                        "games": 19,
                        "goals": 8,
                        "assists": 16,
                        "points": 24,
                        "points_per_game": 1.263,
                    },
                    "why_high": ["Role rank 1"],
                    "risk_flags": ["Shortened sample"],
                },
                {
                    "header": {"name": "Alexei Medvedev"},
                    "stat_evidence": {
                        "role_group": "goalie",
                        "goalie_games": 67,
                        "goalie_save_percentage": 0.909,
                        "goalie_goals_against_average": 3.37,
                        "goalie_shutouts": 3,
                    },
                    "why_high": ["Goalie metrics"],
                    "risk_flags": [],
                },
            ]
        ),
        encoding="utf-8",
    )

    report = write_demo_sanity_report(demo_dir, tmp_path / "sanity")

    assert len(report.top_overall) == 2
    assert len(report.top_defense) == 1
    assert len(report.top_goalies) == 1
    assert (tmp_path / "sanity" / "summary.md").exists()
    story_rows = list(csv.DictReader((tmp_path / "sanity" / "story_player_checks.csv").open()))
    assert story_rows[0]["name"] == "Matthew Schaefer"
    assert "19 GP" in story_rows[0]["stat_evidence"]
    assert "0.909 SV%" in story_rows[3]["stat_evidence"]
