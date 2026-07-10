import csv

from draft_room_intelligence.data.chl_stats import (
    ChlStatSource,
    enrich_chl_stats,
    parse_chl_goalies_html,
    parse_chl_skaters_html,
)
from draft_room_intelligence.data.eliteprospects_csv import PLAYER_COLUMNS, SEASON_STAT_LINE_COLUMNS, write_table


HTML = '''
<table id="topskaters"><tbody></tbody></table>
<script>
$('#topskaters').DataTable({
  data: [[1,"C","77","","",["https:\\/\\/chl.ca\\/ohl\\/players\\/8769","Misa, Michael"],[["https:\\/\\/chl.ca\\/ohl\\/roster\\/34\\/79","SAG"]],"65","62","72","134"]]
});
</script>
'''

PLAYOFF_HTML = '''
<table id="topskaters"><tbody></tbody></table>
<script>
$('#topskaters').DataTable({
  data: [[1,"C","77","","",["https:\\/\\/chl.ca\\/ohl\\/players\\/8769","Misa, Michael"],[["https:\\/\\/chl.ca\\/ohl\\/roster\\/34\\/79","SAG"]],"11","10","14","24"]]
});
</script>
'''

GOALIE_HTML = '''
<table id="topgoalies"><tbody></tbody></table>
<script>
$('#topgoalies').DataTable({
  data: [[1,"G","32","","",["https:\\/\\/chl.ca\\/ohl\\/players\\/8819","George, Carter"],[["https:\\/\\/chl.ca\\/ohl\\/roster\\/11\\/79","OS"]],"47",2705,"1665","1514","151","0","3.35","0.909","17","22","3"]]
});
</script>
'''


def test_parse_chl_skaters_html_extracts_core_stats():
    rows = parse_chl_skaters_html(
        HTML,
        ChlStatSource(
            league="OHL",
            season="2024-25",
            source_url="https://chl.ca/ohl/stats/players/79/all/points/all",
        ),
    )

    assert len(rows) == 1
    assert rows[0].name == "Michael Misa"
    assert rows[0].source_id == "8769"
    assert rows[0].team == "SAG"
    assert rows[0].games == "65"
    assert rows[0].goals == "62"
    assert rows[0].assists == "72"
    assert rows[0].points == "134"
    assert rows[0].regular_season is True


def test_parse_chl_goalies_html_extracts_exposure_without_skater_points():
    rows = parse_chl_goalies_html(
        GOALIE_HTML,
        ChlStatSource(
            league="OHL",
            season="2024-25",
            source_url="https://chl.ca/ohl/stats/goalies/79/all/gaa/all",
        ),
    )

    assert len(rows) == 1
    assert rows[0].name == "Carter George"
    assert rows[0].source_id == "8819"
    assert rows[0].team == "OS"
    assert rows[0].games == "47"
    assert rows[0].goals == ""
    assert rows[0].assists == ""
    assert rows[0].points == ""
    assert rows[0].regular_season is True
    assert rows[0].goalie_minutes == "2705"
    assert rows[0].shots_against == "1665"
    assert rows[0].saves == "1514"
    assert rows[0].goals_against == "151"
    assert rows[0].save_percentage == "0.909"
    assert rows[0].goals_against_average == "3.35"
    assert rows[0].wins == "17"
    assert rows[0].losses == "22"
    assert rows[0].ties == "3"
    assert rows[0].shutouts == "0"


def test_enrich_chl_stats_replaces_matching_placeholder_rows(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "ohl.html"
    base_dir.mkdir()
    source_path.write_text(HTML, encoding="utf-8")
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-002-michael-misa",
                "name": "Michael Misa",
                "birth_date": "",
                "nationality": "Canada",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-002-michael-misa",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-002-michael-misa",
                "season": "2024-25",
                "league": "OHL",
                "team": "Saginaw Spirit",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-002-michael-misa",
                "source_url": "",
            }
        ],
    )

    summary = enrich_chl_stats(
        base_dir,
        output_dir,
        [
            ChlStatSource(
                league="OHL",
                season="2024-25",
                source_url="https://chl.ca/ohl/stats/players/79/all/points/all",
                source_path=source_path,
            )
        ],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))
    with (output_dir / "chl_stat_matches.csv").open(newline="", encoding="utf-8") as file:
        matches = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 1
    assert stat_lines[0]["source"] == "chl"
    assert stat_lines[0]["games"] == "65"
    assert stat_lines[0]["points"] == "134"
    assert matches[0]["matched"] == "true"


def test_enrich_chl_stats_keeps_regular_and_playoff_rows(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    regular_path = tmp_path / "ohl_regular.html"
    playoff_path = tmp_path / "ohl_playoffs.html"
    base_dir.mkdir()
    regular_path.write_text(HTML, encoding="utf-8")
    playoff_path.write_text(PLAYOFF_HTML, encoding="utf-8")
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-002-michael-misa",
                "name": "Michael Misa",
                "birth_date": "",
                "nationality": "Canada",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-002-michael-misa",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-002-michael-misa",
                "season": "2024-25",
                "league": "OHL",
                "team": "Saginaw Spirit",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-002-michael-misa",
                "source_url": "",
            }
        ],
    )

    summary = enrich_chl_stats(
        base_dir,
        output_dir,
        [
            ChlStatSource(
                league="OHL",
                season="2024-25",
                source_url="https://chl.ca/ohl/stats/players/79/all/points/all",
                source_path=regular_path,
            ),
            ChlStatSource(
                league="OHL",
                season="2024-25",
                source_url="https://chl.ca/ohl/stats/players/79/playoffs/points/all",
                regular_season=False,
                source_path=playoff_path,
            ),
        ],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 2
    assert {row["regular_season"] for row in stat_lines} == {"true", "false"}
    playoff = [row for row in stat_lines if row["regular_season"] == "false"][0]
    assert playoff["games"] == "11"
    assert playoff["points"] == "24"
