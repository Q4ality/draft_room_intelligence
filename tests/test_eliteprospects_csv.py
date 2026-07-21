from pathlib import Path

from draft_room_intelligence.data.eliteprospects_csv import (
    format_eliteprospects_validation_report,
    normalize_eliteprospects_export,
    validate_eliteprospects_export,
    write_eliteprospects_normalized_tables,
)

FIXTURE = Path(__file__).parent / "fixtures" / "eliteprospects_export.csv"


def test_validate_eliteprospects_export_reports_shape_and_warnings():
    report = validate_eliteprospects_export(FIXTURE)

    assert report.rows == 2
    assert report.unique_players == 1
    assert report.stat_line_rows == 2
    assert report.missing_name_rows == 0
    assert report.missing_stat_context_rows == 0
    assert report.missing_games_rows == 0
    assert report.missing_points_rows == 0
    assert report.duplicate_player_ids == ("209490",)
    assert not report.has_errors
    assert report.has_warnings
    assert "duplicate_player_ids: 209490" in format_eliteprospects_validation_report(report)


def test_normalize_eliteprospects_export_maps_players_and_stat_lines():
    normalized = normalize_eliteprospects_export(FIXTURE, draft_year=2019)

    assert normalized.players == [
        {
            "player_id": "2019-ep-209490",
            "name": "Alex Turcotte",
            "birth_date": "2001-02-26",
            "nationality": "USA",
            "position": "C",
            "handedness": "L",
            "height_cm": "180",
            "weight_kg": "88",
            "age_at_draft": "18.31",
            "source": "eliteprospects",
            "source_id": "209490",
            "source_url": "https://www.eliteprospects.com/player/201747/alex-turcotte",
        }
    ]
    assert len(normalized.season_stat_lines) == 2
    ushl_line = next(
        line
        for line in normalized.season_stat_lines
        if line["league"] == "USHL" and line["team"] == "U.S. National Under-18 Team"
    )
    assert ushl_line["source"] == "eliteprospects"
    assert ushl_line["timing"] == "pre_draft"
    assert ushl_line["points"] == "34"


def test_write_eliteprospects_normalized_tables(tmp_path):
    normalized = write_eliteprospects_normalized_tables(
        FIXTURE,
        tmp_path,
        draft_year=2019,
    )

    assert len(normalized.players) == 1
    assert (tmp_path / "players.csv").exists()
    assert (tmp_path / "season_stat_lines.csv").exists()
    assert "eliteprospects" in (tmp_path / "players.csv").read_text(encoding="utf-8")


def test_normalize_eliteprospects_export_canonicalizes_leagues_and_infers_playoffs(tmp_path):
    fixture = tmp_path / "ep_aliases.csv"
    fixture.write_text(
        "\n".join(
            [
                "EP Player ID,Name,Position,Season,League,Team,GP,G,A,TP,Stage",
                "999,Example Skater,D,2018-19,Swe-1,Modo,10,1,4,5,Regular Season",
                "999,Example Skater,D,2018-19,Rus-MHL,Loko,6,1,5,6,Playoffs",
            ]
        ),
        encoding="utf-8",
    )

    normalized = normalize_eliteprospects_export(fixture, draft_year=2019)

    assert len(normalized.season_stat_lines) == 2
    by_league = {line["league"]: line for line in normalized.season_stat_lines}
    assert by_league["MHL"]["regular_season"] == "false"
    assert by_league["HockeyAllsvenskan"]["regular_season"] == "true"
