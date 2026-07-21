import csv
import json

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.europe_stats import (
    EuropeStatSource,
    enrich_europe_stats,
    parse_khl_html,
    parse_liiga,
    parse_swehockey,
)

SWEHOCKEY_HTML = """
<table class="tblContent">
<tr><th class="tdTitle">Djurgardens IF</th></tr>
<tr><th class="tdSubTitle">Playing Statistics</th></tr>
<tr><th>Rk</th><th>Name</th><th>Pos</th><th>GP</th><th>G</th><th>A</th><th>TP</th>
<th>PIM</th><th>+/-</th><th>SOG</th><th>FO+</th><th>FO-</th><th>FO%</th></tr>
<tr><td>1</td><td>Nilson, Eric</td><td>CE</td><td>37</td><td>12</td><td>26</td><td>38</td>
<td>10</td><td>18</td><td>90</td><td>210</td><td>190</td><td>52.5</td></tr>
</table>
<table class="tblContent">
<tr><th class="tdSubTitle">Goalkeeping Statistics</th></tr>
<tr><th>Rk</th><th>Name</th><th>GPI</th><th>MIP</th><th>GA</th><th>SVS</th>
<th>SOG</th><th>SVS%</th><th>GAA</th><th>SO</th><th>W</th><th>L</th></tr>
<tr><td>1</td><td>Goalie, Sample</td><td>20</td><td>1200:00</td><td>40</td><td>500</td>
<td>540</td><td>92.59</td><td>2.00</td><td>3</td><td>14</td><td>4</td></tr>
</table>
"""


def test_parse_swehockey_preserves_skater_and_goalie_context():
    lines = parse_swehockey(
        SWEHOCKEY_HTML,
        EuropeStatSource("2024-25", "swehockey", "Sweden Jrs.", "https://example.test"),
    )

    assert len(lines) == 2
    assert lines[0].name == "Eric Nilson"
    assert lines[0].plus_minus == "18"
    assert lines[0].shots == "90"
    assert lines[0].faceoff_percentage == "52.5"
    assert lines[1].name == "Sample Goalie"
    assert lines[1].save_percentage == "0.926"


def test_parse_liiga_json_preserves_advanced_stats():
    raw = json.dumps(
        [
            {
                "playerId": 10,
                "firstName": "Konsta",
                "lastName": "Helenius",
                "teamName": "Jukurit",
                "games": 51,
                "goals": 17,
                "assists": 30,
                "points": 47,
                "plusMinus": 8,
                "shots": 120,
                "contestWon": 300,
                "contestLost": 270,
                "contestWonPercentage": 52.63,
            }
        ]
    )

    lines = parse_liiga(
        raw,
        EuropeStatSource("2023-24", "liiga", "Liiga", "https://example.test", kind="skaters"),
    )

    assert lines[0].points == "47"
    assert lines[0].shots == "120"
    assert lines[0].faceoff_wins == "300"


def test_parse_cached_khl_table():
    raw = """
    <table><tr><th>Player</th><th>Team</th><th>GP</th><th>G</th><th>A</th>
    <th>PTS</th><th>+/-</th></tr><tr><td>Alexander Zharovsky</td><td>Salavat</td>
    <td>7</td><td>0</td><td>1</td><td>1</td><td>2</td></tr></table>
    """

    lines = parse_khl_html(
        raw,
        EuropeStatSource("2024-25", "khl", "KHL", "https://example.test"),
    )

    assert lines[0].name == "Alexander Zharovsky"
    assert lines[0].plus_minus == "2"


def test_enrichment_matches_within_country_family_and_writes_advanced_table(tmp_path):
    base = tmp_path / "base"
    output = tmp_path / "output"
    base.mkdir()
    write_table(
        base / "players.csv",
        PLAYER_COLUMNS,
        [{"player_id": "p1", "name": "Eric Nilson", "position": "C", "source": "test"}],
    )
    write_table(
        base / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "Sweden Jrs.",
                "team": "Djurgardens IF",
                "games": "40",
                "points": "45",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "old",
            }
        ],
    )
    cache = tmp_path / "sweden.html"
    cache.write_text(SWEHOCKEY_HTML, encoding="utf-8")

    summary = enrich_europe_stats(
        base,
        output,
        [
            EuropeStatSource(
                "2024-25",
                "swehockey",
                "Sweden Jrs.",
                "https://example.test",
                source_path=cache,
            )
        ],
    )

    stats = list(csv.DictReader((output / "season_stat_lines.csv").open(encoding="utf-8")))
    advanced = list(csv.DictReader((output / "advanced_stat_lines.csv").open(encoding="utf-8")))
    assert summary.matched_players == 1
    assert stats[0]["points"] == "45"
    assert stats[0]["source"] == "old"
    assert advanced[0]["games"] == "37"
    assert advanced[0]["plus_minus"] == "18"
    assert advanced[0]["source"] == "swehockey"


def test_enrichment_matches_cyrillic_russian_name_with_audited_method(tmp_path):
    base = tmp_path / "base"
    output = tmp_path / "output"
    base.mkdir()
    write_table(
        base / "players.csv",
        PLAYER_COLUMNS,
        [{"player_id": "p1", "name": "Alexander Zharovsky", "position": "C", "source": "test"}],
    )
    write_table(
        base / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "MHL",
                "team": "Tolpar",
                "timing": "pre_draft",
            }
        ],
    )
    cache = tmp_path / "mhl.html"
    cache.write_text(
        "<table><tr><th>Player</th><th>Team</th><th>GP</th><th>G</th><th>A</th><th>PTS</th></tr>"
        "<tr><td>Александр Жаровский</td><td>Tolpar</td><td>45</td><td>24</td><td>26</td><td>50</td></tr></table>",
        encoding="utf-8",
    )

    summary = enrich_europe_stats(
        base,
        output,
        [EuropeStatSource("2024-25", "khl", "MHL", "https://example.test", source_path=cache)],
    )

    matches = list(csv.DictReader((output / "europe_stat_matches.csv").open(encoding="utf-8")))
    assert summary.matched_players == 1
    assert matches[0]["matched"] == "true"
    assert matches[0]["match_method"] == "transliterated_name"
