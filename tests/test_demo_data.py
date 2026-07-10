from draft_room_intelligence.data.demo_data import audit_demo_class
from draft_room_intelligence.data.demo_data import format_demo_audit_report
from draft_room_intelligence.data.demo_data import scaffold_demo_class


def test_scaffold_demo_class_creates_expected_templates(tmp_path):
    paths = scaffold_demo_class(tmp_path, 2025)

    assert paths.hockeydb_player_pages_dir.exists()
    assert paths.processed_demo_dir.exists()
    assert paths.outputs_dir.exists()
    assert paths.match_map_csv.exists()
    assert paths.featured_players_csv.exists()

    match_map_header = paths.match_map_csv.read_text(encoding="utf-8").splitlines()[0]
    featured_header = paths.featured_players_csv.read_text(encoding="utf-8").splitlines()[0]

    assert match_map_header == "source_player_id,base_player_id,note"
    assert featured_header == "player_id,player_name,demo_role,story_hook,priority,notes"


def test_audit_demo_class_reports_missing_and_present_inputs(tmp_path):
    paths = scaffold_demo_class(tmp_path, 2025)
    paths.hockeydb_draft_html.write_text("<html></html>", encoding="utf-8")
    (paths.hockeydb_player_pages_dir / "player-1.html").write_text("<html></html>", encoding="utf-8")
    paths.eliteprospects_csv.parent.mkdir(parents=True, exist_ok=True)
    paths.eliteprospects_csv.write_text("EP Player ID,Player\n1,Example\n", encoding="utf-8")

    report = audit_demo_class(tmp_path, 2025)
    text = format_demo_audit_report(report)

    assert report.ready_for_etl is True
    assert report.strong_for_demo is True
    assert "HockeyDB draft HTML: present" in text
    assert "Elite Prospects export: present" in text
    assert "Next step: Run ETL and build the demo package/site." in text
    assert "Build demo site:" in text


def test_audit_demo_class_flags_missing_required_assets(tmp_path):
    report = audit_demo_class(tmp_path, 2025)
    text = format_demo_audit_report(report)

    assert report.ready_for_etl is False
    assert "Ready for ETL: no" in text
    assert "HockeyDB draft HTML: missing" in text
    assert "## Missing Required Inputs" in text
    assert "Collect the required raw inputs, then re-run the audit." in text
