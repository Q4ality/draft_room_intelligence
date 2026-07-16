import json
from pathlib import Path

from draft_room_intelligence.cli import run_build_demo_site
from draft_room_intelligence.cli import run_export_demo_package
from draft_room_intelligence.data.historical_csv import load_historical_prospects_csv
from draft_room_intelligence.domain import HistoricalProspect
from draft_room_intelligence.domain import PreDraftStatLine
from draft_room_intelligence.reports.demo_export import build_demo_export_bundle
from draft_room_intelligence.reports.demo_export import build_stat_evidence
from draft_room_intelligence.reports.demo_export import build_team_fit
from draft_room_intelligence.reports.demo_export import evidence_weighted_board_score
from draft_room_intelligence.reports.demo_export import scouting_qualitative_flags
from draft_room_intelligence.reports.demo_export import TeamFitContext


FIXTURE = Path(__file__).parent / "fixtures" / "historical_prospects.csv"


def test_build_demo_export_bundle_returns_board_and_player_payloads():
    prospects = load_historical_prospects_csv(FIXTURE)

    bundle = build_demo_export_bundle(prospects)

    assert len(bundle.board_rows) == 2
    assert len(bundle.compare_rows) == 2
    assert len(bundle.player_details) == 2
    first = bundle.board_rows[0]
    assert first["disagreement_bucket"] in {"aligned", "model_higher", "consensus_higher"}
    assert first["evidence_depth"] in {"low", "medium", "high"}
    assert first["short_reason"]
    assert first["risk_note"]
    assert bundle.manifest["player_count"] == 2
    assert "dataset_status" in bundle.manifest


def test_evidence_weighted_board_score_keeps_low_evidence_near_consensus():
    feature = {
        "role_group": "forward",
        "pre_draft_total_games": "0",
        "pre_draft_row_count": "1",
        "pre_draft_league_count": "1",
    }

    score = evidence_weighted_board_score(1.0, 0.5, feature)

    assert abs(score - 0.59) < 0.000001


def test_evidence_weighted_board_score_protects_elite_defense_short_sample():
    feature = {
        "role_group": "defense",
        "pre_draft_total_games": "19",
        "pre_draft_row_count": "2",
        "pre_draft_league_count": "2",
    }

    score = evidence_weighted_board_score(0.72, 1.0, feature)

    assert score > 0.92


def test_team_fit_reason_surfaces_u25_peer_pipeline_examples():
    prospect = HistoricalProspect(
        player_id="p1",
        name="Center Prospect",
        draft_year=2025,
        position="C",
        age_at_draft=18.0,
        height_cm=183,
        weight_kg=82,
        consensus_rank=10,
        stat_line=PreDraftStatLine(league="OHL", team="T", season="2024-25", games=50, goals=20, assists=30),
    )
    context = TeamFitContext(
        team_id="DET",
        team_name="Detroit Red Wings",
        depth_rows=[
            {
                "league_level": "NHL",
                "role_bucket": "center",
                "role_type": "scoring_center",
                "players": "1",
                "under_25": "0",
                "avg_age": "30.0",
                "scarcity_score": "0.500",
                "scarcity_target": "2.0",
                "example_players": "Dylan Larkin",
            },
            {
                "league_level": "NHL",
                "role_bucket": "center",
                "role_type": "center_depth",
                "players": "4",
                "under_25": "2",
                "avg_age": "25.2",
                "scarcity_score": "0.000",
                "scarcity_target": "4.0",
                "example_players": "Marco Kasper; Emmitt Finnie",
            },
        ],
    )

    fit = build_team_fit(prospect, context, tool_score=0.8)

    assert "Current role examples: Dylan Larkin" in str(fit["reason"])
    assert "U25 peer pipeline examples: Marco Kasper" in str(fit["reason"])


def test_scouting_qualitative_flags_capture_championship_role_context():
    prospect = HistoricalProspect(
        player_id="p2",
        name="Nikita Tyurin",
        draft_year=2025,
        position="D",
        age_at_draft=18.0,
        height_cm=183,
        weight_kg=79,
        consensus_rank=140,
        stat_line=PreDraftStatLine(league="MHL", team="MHK Spartak Moskva", season="2024-25", games=1, goals=0, assists=0),
        scouting_text="A puck-moving defender who earned an important role on a championship contender.",
    )
    board_row = {
        "role_group": "defense",
        "goalie_quality_score": "0.000000",
    }

    flags = scouting_qualitative_flags(prospect)
    evidence = build_stat_evidence(prospect, board_row, flags)

    assert "EP role flag: championship-team context" in flags
    assert "EP role flag: important team role" in evidence["qualitative_flags"]


def test_run_export_demo_package_writes_demo_artifacts(capsys, tmp_path):
    run_export_demo_package(FIXTURE, tmp_path)

    output = capsys.readouterr().out
    board_path = tmp_path / "board.csv"
    compare_path = tmp_path / "compare.csv"
    players_path = tmp_path / "players.json"
    manifest_path = tmp_path / "manifest.json"

    assert "# Demo package export:" in output
    assert "Prospects loaded: 2" in output
    assert board_path.exists()
    assert compare_path.exists()
    assert players_path.exists()
    assert manifest_path.exists()

    board_csv = board_path.read_text(encoding="utf-8")
    players = json.loads(players_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "board_rank" in board_csv
    assert "disagreement_bucket" in board_csv
    assert "drafted_team_id" in board_csv
    assert "drafted_team_name" in board_csv
    assert len(players) == 2
    assert "why_high" in players[0]
    assert "stat_evidence" in players[0]
    assert manifest["player_count"] == 2
    assert "demo_story_players" in manifest


def test_run_build_demo_site_writes_html(capsys, tmp_path):
    run_build_demo_site(FIXTURE, tmp_path)

    output = capsys.readouterr().out
    html_path = tmp_path / "index.html"

    assert "# Demo site build:" in output
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "Draft Room Intelligence Demo" in html
    assert "Single-Class Demo" in html
    assert "Load Story Shortlist" in html
    assert "Export Summary HTML" in html
    assert "Guided Stories" in html
    assert "Source Trace" in html
    assert "source-link" in html
    assert "filter-drafted-team" in html
    assert "Drafted Team" in html
    assert "NHL-ready U25" in html
    assert "AHL/prospect U25" in html
