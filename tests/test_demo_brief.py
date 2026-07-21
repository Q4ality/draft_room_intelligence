from pypdf import PdfReader

from draft_room_intelligence.reports.demo_brief import write_demo_meeting_brief
from draft_room_intelligence.reports.demo_export import DemoExportBundle


def test_write_demo_meeting_brief_creates_single_page_six_story_artifacts(tmp_path):
    board_rows = []
    player_details = []
    stories = []
    for index in range(1, 7):
        player_id = f"p{index}"
        board_rows.append(
            {
                "player_id": player_id,
                "name": f"Player {index}",
                "position": "G" if index == 4 else "C",
                "primary_league": "OHL",
                "primary_league_family": "Canadian Junior",
                "board_rank": str(index),
                "consensus_rank": str(index + 1),
                "board_score": "0.900",
                "team_adjusted_score": "0.850",
                "team_fit_score": "0.600",
                "team_fit_need": "Useful team fit",
                "team_fit_team": "NYI",
                "evidence_depth": "high",
            }
        )
        player_details.append(
            {
                "player_id": player_id,
                "stat_evidence": {
                    "role_group": "goalie" if index == 4 else "forward",
                    "games": 50,
                    "goals": 20,
                    "assists": 30,
                    "points": 50,
                    "points_per_game": 1.0,
                    "goalie_save_percentage": 0.925,
                    "goalie_goals_against_average": 2.1,
                    "goalie_wins": 30,
                    "goalie_losses": 15,
                    "goalie_shutouts": 4,
                },
                "risk_flags": ["Review sample translation."],
                "team_fit": {
                    "need": "Useful team fit",
                    "team_name": "New York Islanders",
                    "score": 0.6,
                },
                "pre_draft_history": [{"source": "league-source"}],
            }
        )
        stories.append(
            {
                "player_id": player_id,
                "story_role": f"Story {index}",
                "story_hook": "A concise evidence-backed discussion anchor.",
            }
        )
    bundle = DemoExportBundle(
        board_rows=board_rows,
        compare_rows=[],
        player_details=player_details,
        manifest={
            "draft_year": 2025,
            "dataset_status": "strong",
            "demo_story_players": stories,
        },
    )

    outputs = write_demo_meeting_brief(tmp_path, bundle)

    assert outputs.player_count == 6
    assert outputs.html_path.exists()
    rendered_html = outputs.html_path.read_text(encoding="utf-8")
    assert "Player 1" in rendered_html
    assert "0.925 SV%, 2.10 GAA, 30-15, 4 SO" in rendered_html
    assert outputs.pdf_path.stat().st_size > 1_000
    assert len(PdfReader(outputs.pdf_path).pages) == 1
