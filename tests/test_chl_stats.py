import csv

from draft_room_intelligence.data.chl_stats import (
    ChlStatSource,
    enrich_chl_stats,
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
