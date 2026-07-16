import csv
import json

from draft_room_intelligence.data.team_rosters import write_roster_csv
from draft_room_intelligence.data.team_rosters import RosterPlayer
from draft_room_intelligence.reports.team_system_audit import write_team_system_audit


def test_write_team_system_audit_flags_saturated_pipeline_and_goalie_assignment(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    demo_dir = tmp_path / "demo"
    output_dir = tmp_path / "audit"
    demo_dir.mkdir()
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer("SJS", "San Jose Sharks", "NHL", "", "celebrini", "Macklin Celebrini", "C", age=20.1, games=82),
            RosterPlayer("SJS", "San Jose Sharks", "NHL", "", "smith", "Will Smith", "C", age=21.3, games=69),
            RosterPlayer("SJS", "San Jose Sharks", "AHL", "San Jose Barracuda", "ostapchuk", "Zack Ostapchuk", "C", age=22.3, games=15),
            RosterPlayer("PIT", "Pittsburgh Penguins", "NHL", "", "silovs", "Arturs Silovs", "G", age=25.3, games=39),
            RosterPlayer("PIT", "Pittsburgh Penguins", "AHL", "Wilkes-Barre/Scranton Penguins", "murashov", "Sergei Murashov", "G", age=21.5, games=16),
            RosterPlayer("PIT", "Pittsburgh Penguins", "AHL", "Wilkes-Barre/Scranton Penguins", "blomqvist", "Joel Blomqvist", "G", age=23.7, games=18),
        ],
    )
    (demo_dir / "manifest.json").write_text(
        json.dumps(
            {
                "team_contexts": [
                    {"team_id": "SJS", "team_name": "San Jose Sharks"},
                    {"team_id": "PIT", "team_name": "Pittsburgh Penguins"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (demo_dir / "players.json").write_text(
        json.dumps(
            [
                {
                    "header": {"name": "Draft Center", "position": "C"},
                    "team_fit_options": [
                        {"team_id": "SJS", "score": 0.72, "pipeline_need_score": 0.80}
                    ],
                },
                {
                    "header": {"name": "Draft Goalie", "position": "G"},
                    "team_fit_options": [
                        {"team_id": "PIT", "score": 0.66, "pipeline_need_score": 0.70}
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )

    audit = write_team_system_audit(roster_csv, demo_dir, output_dir)

    assert any(
        row["team_id"] == "SJS" and row["issue_type"] == "high_fit_despite_saturated_u25_pipeline"
        for row in audit.flag_rows
    )
    assert any(
        row["team_id"] == "SJS" and row["issue_type"] == "high_fit_despite_nhl_ready_u25_pipeline"
        for row in audit.flag_rows
    )
    assert any(
        row["team_id"] == "PIT" and row["issue_type"] == "goalie_fit_high_despite_multiple_u25_goalies"
        for row in audit.flag_rows
    )
    rows = list(csv.DictReader((output_dir / "team_bucket_audit.csv").open(newline="", encoding="utf-8")))
    sjs_center = [row for row in rows if row["team_id"] == "SJS" and row["role_bucket"] == "center"][0]
    assert sjs_center["u25_players"] == "3"
    assert sjs_center["nhl_ready_u25"] == "2"
    assert sjs_center["ahl_pipeline_u25"] == "1"
    assert "Macklin Celebrini" in sjs_center["young_core"]
    assert "Macklin Celebrini" in sjs_center["nhl_ready_young_core"]
    assert "Zack Ostapchuk" in sjs_center["ahl_pipeline_young_core"]
