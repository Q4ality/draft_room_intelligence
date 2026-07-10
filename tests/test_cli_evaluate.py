from pathlib import Path

from draft_room_intelligence.cli import run_generate_match_map_template
from draft_room_intelligence.cli import run_import_eliteprospects
from draft_room_intelligence.cli import run_merge_eliteprospects
from draft_room_intelligence.cli import run_process_eliteprospects
from draft_room_intelligence.cli import run_report_merge_quality
from draft_room_intelligence.cli import run_validate_eliteprospects
from draft_room_intelligence.cli import run_evaluate
from draft_room_intelligence.cli import run_evaluate_role_models
from draft_room_intelligence.cli import run_etl_draft_year
from draft_room_intelligence.cli import run_export_feature_table


FIXTURE = Path(__file__).parent / "fixtures" / "historical_prospects.csv"
PILOT = Path(__file__).parents[1] / "data" / "processed" / "pilot_2019"
ELITEPROSPECTS_FIXTURE = Path(__file__).parent / "fixtures" / "eliteprospects_export.csv"
HOCKEYDB_DRAFT_FIXTURE = Path(__file__).parent / "fixtures" / "hockeydb_2019_draft_sample.html"
HOCKEYDB_PLAYER_PAGES_FIXTURE = Path(__file__).parent / "fixtures" / "hockeydb_player_pages"


def test_run_evaluate_prints_consensus_report(capsys):
    run_evaluate(FIXTURE, baseline="consensus", precision_n=1)

    output = capsys.readouterr().out

    assert "# Consensus baseline evaluation:" in output
    assert "Prospects loaded: 2" in output
    assert "## nhler" in output
    assert "- precision_at_n: 1.000" in output
    assert "## rank" in output


def test_run_evaluate_prints_projection_report(capsys):
    run_evaluate(FIXTURE, baseline="projection", precision_n=1)

    output = capsys.readouterr().out

    assert "# Projection baseline evaluation:" in output
    assert "Prospects loaded: 2" in output
    assert "## impact" in output


def test_run_evaluate_prints_normalized_table_report(capsys):
    run_evaluate(PILOT, baseline="consensus", precision_n=25)

    output = capsys.readouterr().out

    assert "# Consensus baseline evaluation:" in output
    assert "Prospects loaded: 217" in output
    assert "Precision@N: 25" in output


def test_run_evaluate_prints_adjusted_production_report(capsys):
    run_evaluate(PILOT, baseline="adjusted-production", precision_n=25)

    output = capsys.readouterr().out

    assert "# Adjusted-Production baseline evaluation:" in output
    assert "Prospects loaded: 217" in output
    assert "## rank" in output


def test_run_evaluate_prints_hybrid_report(capsys):
    run_evaluate(PILOT, baseline="hybrid", precision_n=25)

    output = capsys.readouterr().out

    assert "# Hybrid baseline evaluation:" in output
    assert "Prospects loaded: 217" in output
    assert "## rank" in output


def test_run_import_eliteprospects_prints_import_summary(capsys, tmp_path):
    run_import_eliteprospects(
        ELITEPROSPECTS_FIXTURE,
        tmp_path,
        draft_year=2019,
        timing="pre_draft",
    )

    output = capsys.readouterr().out

    assert "# Elite Prospects import:" in output
    assert "Players written: 1" in output
    assert "Season stat lines written: 2" in output


def test_run_validate_eliteprospects_prints_validation_report(capsys):
    run_validate_eliteprospects(ELITEPROSPECTS_FIXTURE)

    output = capsys.readouterr().out

    assert "# Elite Prospects Export Validation" in output
    assert "rows: 2" in output
    assert "unique_players: 1" in output
    assert "duplicate_player_ids: 209490" in output


def test_run_merge_eliteprospects_prints_merge_summary(capsys, tmp_path):
    eliteprospects_dir = tmp_path / "eliteprospects"
    run_import_eliteprospects(
        ELITEPROSPECTS_FIXTURE,
        eliteprospects_dir,
        draft_year=2019,
        timing="pre_draft",
    )

    run_merge_eliteprospects(
        PILOT,
        eliteprospects_dir,
        tmp_path / "merged",
        replace_timing="pre_draft",
        match_map=None,
    )

    output = capsys.readouterr().out

    assert "# Elite Prospects merge:" in output
    assert "Base players: 217" in output
    assert "Elite Prospects players: 1" in output
    assert "Matched players: 1" in output
    assert "Manual matches: 0" in output
    assert "Name matches: 1" in output


def test_run_report_merge_quality_prints_quality_report(capsys, tmp_path):
    eliteprospects_dir = tmp_path / "eliteprospects"
    merged_dir = tmp_path / "merged"
    run_import_eliteprospects(
        ELITEPROSPECTS_FIXTURE,
        eliteprospects_dir,
        draft_year=2019,
        timing="pre_draft",
    )
    run_merge_eliteprospects(
        PILOT,
        eliteprospects_dir,
        merged_dir,
        replace_timing="pre_draft",
        match_map=None,
    )

    run_report_merge_quality(
        PILOT,
        eliteprospects_dir,
        merged_dir,
        source_name="eliteprospects",
        timing="pre_draft",
    )

    output = capsys.readouterr().out

    assert "# Merge Quality Report" in output
    assert "matched_source_players: 1" in output
    assert "unmatched_source_players: 0" in output
    assert "source_stat_lines_used: 2" in output


def test_run_generate_match_map_template_prints_summary(capsys, tmp_path):
    unmatched = tmp_path / "unmatched_source_players.csv"
    output_path = tmp_path / "match_map_template.csv"
    unmatched.write_text(
        "\n".join(
            [
                "player_id,name,birth_date,nationality,position,handedness,height_cm,weight_kg,age_at_draft,source,source_id,source_url",
                "2019-ep-209490,Alexander Turcotte,,,,,,,,eliteprospects,209490,",
            ]
        ),
        encoding="utf-8",
    )

    run_generate_match_map_template(
        PILOT,
        unmatched,
        output_path,
        candidate_count=3,
    )

    output = capsys.readouterr().out

    assert "# Match map template:" in output
    assert "Unmatched source players: 1" in output
    assert output_path.exists()


def test_run_process_eliteprospects_runs_full_pipeline(capsys, tmp_path):
    source_dir = tmp_path / "eliteprospects"
    merged_dir = tmp_path / "merged"
    template_path = tmp_path / "match_map_template.csv"

    run_process_eliteprospects(
        ELITEPROSPECTS_FIXTURE,
        PILOT,
        source_dir,
        merged_dir,
        draft_year=2019,
        timing="pre_draft",
        replace_timing="pre_draft",
        match_map=None,
        match_template_output=template_path,
        candidate_count=3,
    )

    output = capsys.readouterr().out

    assert "# Elite Prospects processing:" in output
    assert "Imported players: 1" in output
    assert "Matched players: 1" in output
    assert "Template rows: 0" in output
    assert "# Merge Quality Report" in output
    assert (source_dir / "players.csv").exists()
    assert (merged_dir / "players.csv").exists()
    assert template_path.exists()


def test_run_etl_draft_year_without_eliteprospects_copies_base_dataset(capsys, tmp_path):
    run_etl_draft_year(
        PILOT,
        tmp_path / "etl",
        draft_year=2019,
        eliteprospects_csv=None,
        timing="pre_draft",
        replace_timing="pre_draft",
        match_map=None,
        match_template_output=None,
        candidate_count=3,
    )

    output = capsys.readouterr().out

    assert "# Draft-year ETL: 2019" in output
    assert "Elite Prospects enrichment: skipped" in output
    assert (tmp_path / "etl" / "base" / "players.csv").exists()
    assert (tmp_path / "etl" / "final" / "players.csv").exists()


def test_run_etl_draft_year_with_eliteprospects_runs_enrichment(capsys, tmp_path):
    run_etl_draft_year(
        PILOT,
        tmp_path / "etl",
        draft_year=2019,
        eliteprospects_csv=ELITEPROSPECTS_FIXTURE,
        timing="pre_draft",
        replace_timing="pre_draft",
        match_map=None,
        match_template_output=None,
        candidate_count=3,
    )

    output = capsys.readouterr().out

    assert "# Draft-year ETL: 2019" in output
    assert "# Elite Prospects processing:" in output
    assert "Final dataset:" in output
    assert (tmp_path / "etl" / "base" / "players.csv").exists()
    assert (tmp_path / "etl" / "eliteprospects" / "players.csv").exists()
    assert (tmp_path / "etl" / "final" / "players.csv").exists()


def test_run_etl_draft_year_generates_base_from_hockeydb_html(capsys, tmp_path):
    run_etl_draft_year(
        None,
        tmp_path / "etl",
        draft_year=2019,
        hockeydb_draft_html=HOCKEYDB_DRAFT_FIXTURE,
        eliteprospects_csv=None,
        timing="pre_draft",
        replace_timing="pre_draft",
        match_map=None,
        match_template_output=None,
        candidate_count=3,
    )

    output = capsys.readouterr().out
    base_players = (tmp_path / "etl" / "base" / "players.csv").read_text(encoding="utf-8")
    final_rankings = (tmp_path / "etl" / "final" / "rankings.csv").read_text(encoding="utf-8")

    assert "# Draft-year ETL: 2019" in output
    assert "Elite Prospects enrichment: skipped" in output
    assert "Jack Hughes" in base_players
    assert "Kaapo Kakko" in base_players
    assert "draft_slot_proxy" in final_rankings


def test_run_etl_draft_year_uses_cached_hockeydb_player_pages(capsys, tmp_path):
    run_etl_draft_year(
        None,
        tmp_path / "etl",
        draft_year=2019,
        hockeydb_draft_html=HOCKEYDB_DRAFT_FIXTURE,
        hockeydb_player_pages_dir=HOCKEYDB_PLAYER_PAGES_FIXTURE,
        eliteprospects_csv=None,
        timing="pre_draft",
        replace_timing="pre_draft",
        match_map=None,
        match_template_output=None,
        candidate_count=3,
    )

    output = capsys.readouterr().out
    players_csv = (tmp_path / "etl" / "base" / "players.csv").read_text(encoding="utf-8")
    stat_lines_csv = (tmp_path / "etl" / "base" / "season_stat_lines.csv").read_text(encoding="utf-8")

    assert "# Draft-year ETL: 2019" in output
    assert "2001-05-14" in players_csv
    assert "178" in players_csv
    assert "2018-19,USHL,U.S. National U18 Team,50,20,55,75" in stat_lines_csv
    assert "2018-19,USHL,U.S. National U18 Team,28,18,40,58" in stat_lines_csv


def test_run_export_feature_table_writes_csv(capsys, tmp_path):
    output_path = tmp_path / "features.csv"

    run_export_feature_table(PILOT, output_path)

    output = capsys.readouterr().out
    csv_text = output_path.read_text(encoding="utf-8")

    assert "# Feature table export:" in output
    assert "Feature rows written: 217" in output
    assert "player_id,name,draft_year,role_group,position" in csv_text


def test_run_evaluate_role_models_writes_artifacts(capsys, tmp_path):
    feature_output = tmp_path / "features.csv"
    model_output = tmp_path / "models.csv"

    run_evaluate_role_models(
        PILOT,
        feature_output=feature_output,
        model_output=model_output,
        precision_n=25,
    )

    output = capsys.readouterr().out

    assert "# Role-specific model evaluation:" in output
    assert "Prospects loaded: 217" in output
    assert "## nhler" in output
    assert "## board_order" in output
    assert "### top_25" in output
    assert feature_output.exists()
    assert model_output.exists()
