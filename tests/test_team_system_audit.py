import csv
import json

from draft_room_intelligence.data.team_rosters import RosterPlayer, write_roster_csv
from draft_room_intelligence.reports.team_system_audit import (
    bucket_flags,
    bucket_for_position,
    goalie_flags,
    issue_severity,
    write_team_system_audit,
)


def test_audit_position_and_severity_semantics():
    assert bucket_for_position("CLW") == "center"
    assert bucket_for_position("LWC") == "wing"
    assert bucket_for_position("RD") == "defense"
    assert issue_severity("high_fit_despite_ahl_prospect_pipeline") == "medium"


def test_high_priority_fit_flags_require_material_mismatch():
    bucket_row = {
        "role_bucket": "wing",
        "u25_players": "6",
        "nhl_ready_u25": "2",
        "non_nhl_u25": "4",
        "total_players": "12",
        "max_demo_fit_score": "0.61",
        "short_sample_u25": "0",
    }
    goalie_row = {
        "u25_goalies": "2",
        "max_demo_goalie_fit_score": "0.61",
        "low_nhl_game_young_goalies": "",
        "u25_goalie_names": "Goalie One; Goalie Two",
    }

    assert "high_fit_despite_nhl_ready_u25_pipeline" not in bucket_flags(bucket_row)
    assert "high_fit_despite_ahl_prospect_pipeline" in bucket_flags(bucket_row)
    assert "goalie_fit_high_despite_multiple_u25_goalies" not in goalie_flags(goalie_row)


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


def test_team_system_audit_distinguishes_provenance_from_point_in_time_confidence(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    demo_dir = tmp_path / "demo"
    output_dir = tmp_path / "audit"
    demo_dir.mkdir()
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "p1",
                "Season Player",
                "D",
                snapshot_date="2025-06-01",
                snapshot_type="season_participation",
                assignment_confidence="medium",
            )
        ],
    )
    (demo_dir / "manifest.json").write_text(
        json.dumps({"team_contexts": [{"team_id": "NYI", "team_name": "New York Islanders"}]}),
        encoding="utf-8",
    )
    (demo_dir / "players.json").write_text("[]", encoding="utf-8")

    audit = write_team_system_audit(roster_csv, demo_dir, output_dir)
    reliability = audit.reliability_rows[0]

    assert reliability["missing_snapshot_rows"] == "0"
    assert reliability["medium_confidence_rows"] == "1"
    assert "season_participation_not_point_in_time" in reliability["review_flags"]
    summary = (output_dir / "summary.md").read_text(encoding="utf-8")
    assert "High-priority flags: 0" in summary


def test_team_system_contract_coverage_uses_nhl_rows_only(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    demo_dir = tmp_path / "demo"
    output_dir = tmp_path / "audit"
    demo_dir.mkdir()
    players = []
    for player_id in ("1", "2"):
        players.append(
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                player_id,
                f"NHL Player {player_id}",
                "D",
                snapshot_date="2025-06-01",
                cap_hit=1_000_000,
                contract_end_year=2026,
                contract_snapshot_date="2025-06-01",
            )
        )
    players.append(
        RosterPlayer(
            "NYI",
            "New York Islanders",
            "AHL",
            "Bridgeport Islanders",
            "3",
            "AHL Player",
            "D",
            snapshot_date="2025-06-01",
        )
    )
    write_roster_csv(roster_csv, players)
    (demo_dir / "manifest.json").write_text(
        json.dumps({"team_contexts": [{"team_id": "NYI", "team_name": "New York Islanders"}]}),
        encoding="utf-8",
    )
    (demo_dir / "players.json").write_text("[]", encoding="utf-8")

    audit = write_team_system_audit(roster_csv, demo_dir, output_dir)

    reliability = audit.reliability_rows[0]
    assert reliability["players"] == "3"
    assert reliability["nhl_players"] == "2"
    assert reliability["contract_coverage"] == "1.000"
