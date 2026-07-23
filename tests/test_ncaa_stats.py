import csv
import html
import json

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.ncaa_stats import (
    NcaaStatSource,
    enrich_ncaa_stats,
    match_disposition,
    parse_college_hockey_inc,
    parse_uscho,
)
from draft_room_intelligence.data.chl_stats import person_alias_key

CHI_SKATERS = """
<table class="data sortable">
<tr class="stats-section"><td colspan="99"></td></tr>
<tr><th>Rk</th><th>Name</th><th>Team</th><th>Pos.</th><th>Yr</th><th>GP</th>
<th>G</th><th>A</th><th>PTS</th><th>Pt/Gm</th><th>PIM</th><th>Shots</th>
<th>GWG</th><th>PPG</th><th>SHG</th><th>+/-</th><th>Blk</th><th>FW</th><th>FL</th><th>FO%</th></tr>
<tr><td>1</td><td><a href="/players/career/100">James Hagens</a></td><td>Boston College</td>
<td>F</td><td>Fr</td><td>37</td><td>11</td><td>26</td><td>37</td><td>1.0</td>
<td>24</td><td>99</td><td>4</td><td>2</td><td>0</td><td>21</td><td>7</td><td>185</td><td>219</td><td>45.8</td></tr>
</table>
"""

CHI_SKATERS_WITH_GOALIE = CHI_SKATERS.replace(
    "</table>",
    """
<tr><td>2</td><td><a href="/players/career/200">Sample Goalie</a></td>
<td>Providence</td><td>G</td><td>Fr</td><td>19</td><td>0</td><td>0</td>
<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td>
<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
</table>
""",
)


def test_parse_college_hockey_inc_preserves_advanced_stats():
    lines = parse_college_hockey_inc(
        CHI_SKATERS,
        NcaaStatSource("2024-25", "collegehockeyinc", "https://example.test", "skaters"),
    )

    assert len(lines) == 1
    assert lines[0].name == "James Hagens"
    assert lines[0].points == "37"
    assert lines[0].plus_minus == "21"
    assert lines[0].shots == "99"
    assert lines[0].blocks == "7"
    assert lines[0].faceoff_percentage == "45.8"


def test_parse_college_hockey_inc_skater_feed_excludes_goalies():
    lines = parse_college_hockey_inc(
        CHI_SKATERS_WITH_GOALIE,
        NcaaStatSource("2024-25", "collegehockeyinc", "https://example.test", "skaters"),
    )

    assert [line.name for line in lines] == ["James Hagens"]


def test_parse_uscho_combined_payload_extracts_skaters_and_goalies():
    payload = {
        "props": {
            "content": {
                "data": {
                    "scoring": {
                        "data": [
                            {
                                "player_id": 1,
                                "first": "Cale",
                                "last": "Makar",
                                "shortname": "Massachusetts",
                                "gp": 34,
                                "g": 5,
                                "a": 16,
                                "pts": 21,
                                "plsmns": 9,
                            }
                        ]
                    },
                    "goaltending": {
                        "data": [
                            {
                                "player_id": 2,
                                "first": "Sample",
                                "last": "Goalie",
                                "shortname": "Denver",
                                "gp": 20,
                                "min": "1200:00",
                                "saves": 500,
                                "ga": 40,
                                "svp": 0.926,
                                "gaa": 2.0,
                                "w": 14,
                                "l": 4,
                                "t": 2,
                                "sho": 3,
                            }
                        ]
                    },
                }
            }
        }
    }
    raw = f'<div id="app" data-page="{html.escape(json.dumps(payload), quote=True)}"></div>'

    lines = parse_uscho(
        raw,
        NcaaStatSource("2016-17", "uscho", "https://example.test"),
    )

    assert len(lines) == 2
    assert lines[0].name == "Cale Makar"
    assert lines[0].plus_minus == "9"
    assert lines[1].save_percentage == "0.926"
    assert lines[1].shutouts == "3"


def test_enrich_ncaa_writes_basic_and_advanced_tables(tmp_path):
    base = tmp_path / "base"
    output = tmp_path / "out"
    source = tmp_path / "ncaa.html"
    base.mkdir()
    source.write_text(CHI_SKATERS, encoding="utf-8")
    write_table(
        base / "players.csv",
        PLAYER_COLUMNS,
        [{"player_id": "2025-007-james-hagens", "name": "James Hagens", "position": "C"}],
    )
    write_table(
        base / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "season": "2023-24",
                "league": "NCAA",
                "team": "Boston College",
                "games": "2",
                "goals": "0",
                "assists": "1",
                "points": "1",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "curated",
            }
        ],
    )
    with (base / "draft_selections.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["player_id", "drafted_from_league"])
        writer.writeheader()
        writer.writerow({"player_id": "2025-007-james-hagens", "drafted_from_league": "NCAA"})

    summary = enrich_ncaa_stats(
        base,
        output,
        [
            NcaaStatSource(
                "2024-25",
                "collegehockeyinc",
                "https://example.test",
                "skaters",
                source,
            )
        ],
    )

    stats = list(csv.DictReader((output / "season_stat_lines.csv").open()))
    advanced = list(csv.DictReader((output / "advanced_stat_lines.csv").open()))
    assert summary.matched_players == 1
    assert summary.source_availability == "available"
    assert summary.disposition_counts == {"matched": 1}
    assert len(stats) == 2
    current = next(row for row in stats if row["season"] == "2024-25")
    historical = next(row for row in stats if row["season"] == "2023-24")
    assert current["points"] == "37"
    assert historical["source"] == "curated"
    assert advanced[0]["plus_minus"] == "21"
    assert advanced[0]["faceoff_wins"] == "185"


def test_ncaa_match_dispositions_are_explicit():
    assert (
        match_disposition(
            eligible=False,
            name_count=1,
            has_candidates=False,
            source_availability="available",
        )
        == "not_eligible"
    )
    assert (
        match_disposition(
            eligible=True,
            name_count=2,
            has_candidates=True,
            source_availability="available",
        )
        == "ambiguous_identity"
    )
    assert (
        match_disposition(
            eligible=True,
            name_count=1,
            has_candidates=False,
            source_availability="available",
        )
        == "unmatched_in_cached_source"
    )
    assert (
        match_disposition(
            eligible=True,
            name_count=1,
            has_candidates=False,
            source_availability="unavailable",
        )
        == "source_unavailable"
    )
    assert (
        match_disposition(
            eligible=True,
            name_count=1,
            has_candidates=True,
            candidate_identity_count=2,
            source_availability="available",
        )
        == "ambiguous_identity"
    )


def test_ncaa_alias_matching_supports_common_first_name_variants():
    assert person_alias_key("Jack Parsons") == person_alias_key("John Parsons")
    assert person_alias_key("Nick Kempf") == person_alias_key("Nicholas Kempf")
