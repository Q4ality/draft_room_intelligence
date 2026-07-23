import csv
import json

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.europe_stats import (
    EuropeStatLine,
    EuropeStatSource,
    deduplicate_source_lines,
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


def test_swehockey_split_phases_are_aggregated_without_duplicate_season_rows():
    phase_one = EuropeStatLine(
        "Eric Nilson",
        "ericnilson",
        "https://example.test/14709",
        "swehockey",
        "Sweden Jrs.",
        "2023-24",
        True,
        "Djurgardens IF",
        "20",
        "5",
        "10",
        "15",
        plus_minus="4",
        shots="50",
        faceoff_wins="100",
        faceoff_losses="80",
    )
    phase_two = EuropeStatLine(
        "Eric Nilson",
        "ericnilson",
        "https://example.test/15645",
        "swehockey",
        "Sweden Jrs.",
        "2023-24",
        True,
        "Djurgardens IF",
        "18",
        "7",
        "9",
        "16",
        plus_minus="6",
        shots="45",
        faceoff_wins="90",
        faceoff_losses="70",
    )

    lines = deduplicate_source_lines([phase_one, phase_two, phase_one])

    assert len(lines) == 1
    assert lines[0].games == "38"
    assert lines[0].points == "31"
    assert lines[0].plus_minus == "10"
    assert lines[0].shots == "95"
    assert lines[0].faceoff_percentage == "55.9"
    assert lines[0].source_id == "ericnilson@14709+15645"
    assert lines[0].source_url == "https://example.test/14709"


def test_swehockey_split_goalie_phases_preserve_minutes_and_recalculate_rates():
    first = EuropeStatLine(
        "Sample Goalie",
        "samplegoalie",
        "https://example.test/14709",
        "swehockey",
        "Sweden Jrs.",
        "2023-24",
        True,
        "Djurgardens IF",
        "10",
        goalie_minutes="598:30",
        saves="300",
        goals_against="20",
    )
    second = EuropeStatLine(
        "Sample Goalie",
        "samplegoalie",
        "https://example.test/15645",
        "swehockey",
        "Sweden Jrs.",
        "2023-24",
        True,
        "Djurgardens IF",
        "8",
        goalie_minutes="470:30",
        saves="220",
        goals_against="18",
    )

    lines = deduplicate_source_lines([first, second])

    assert len(lines) == 1
    assert lines[0].games == "18"
    assert lines[0].goalie_minutes == "1069"
    assert lines[0].save_percentage == "0.932"
    assert lines[0].goals_against_average == "2.13"


def test_liiga_role_feeds_do_not_double_goalie_totals():
    skater_feed = EuropeStatLine(
        "Sample Goalie",
        "42",
        "https://example.test/basicStats",
        "liiga",
        "Liiga",
        "2023-24",
        True,
        "Jukurit",
        "55",
    )
    goalie_feed = EuropeStatLine(
        "Sample Goalie",
        "42",
        "https://example.test/basicStatsGk",
        "liiga",
        "Liiga",
        "2023-24",
        True,
        "Jukurit",
        "55",
        goalie_minutes="34717",
        saves="1000",
        goals_against="100",
        goals_against_average="2.75",
    )

    lines = deduplicate_source_lines([goalie_feed, skater_feed])

    assert len(lines) == 1
    assert lines[0].games == "55"
    assert lines[0].goalie_minutes == "34717"
    assert lines[0].goals_against_average == "2.75"


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


def test_parse_liiga_goalie_uses_played_games_and_normalizes_api_fields():
    raw = json.dumps(
        [
            {
                "playerId": 42,
                "firstName": "Daniel",
                "lastName": "Salonen",
                "teamName": "Jukurit",
                "goalkeeper": True,
                "games": 6,
                "playedGames": 1,
                "timeOnIce": 138,
                "blockedOrSavedShots": 3,
                "goalsAgainst": 2,
                "savePercentage": 60,
                "goalsAgainstAvg": 52.17,
                "gkWins": 0,
                "gkLosses": 0,
                "gkTies": 0,
                "shutOut": 0,
            }
        ]
    )

    lines = parse_liiga(
        raw,
        EuropeStatSource("2024-25", "liiga", "Liiga", "https://example.test", kind="goalies"),
    )

    assert len(lines) == 1
    assert lines[0].games == "1"
    assert lines[0].goalie_minutes == "2.30"
    assert lines[0].saves == "3"
    assert lines[0].save_percentage == "0.600"
    assert lines[0].goals_against_average == "52.17"


def test_enrichment_replaces_stale_row_from_same_authoritative_provider(tmp_path):
    base = tmp_path / "base"
    output = tmp_path / "output"
    base.mkdir()
    write_table(
        base / "players.csv",
        PLAYER_COLUMNS,
        [{"player_id": "p1", "name": "Daniel Salonen", "position": "G", "source": "test"}],
    )
    write_table(
        base / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "Liiga",
                "team": "Lukko",
                "games": "6",
                "goalie_minutes": "138",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "liiga; eliteprospects_pdf",
            },
            {
                "player_id": "p1",
                "season": "2024-25",
                "league": "Liiga",
                "team": "Lukko",
                "games": "40",
                "goalie_minutes": "2400",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "eliteprospects_pdf",
            },
        ],
    )
    cache = tmp_path / "liiga.json"
    cache.write_text(
        json.dumps(
            [
                {
                    "playerId": 42,
                    "firstName": "Daniel",
                    "lastName": "Salonen",
                    "teamName": "Lukko",
                    "goalkeeper": True,
                    "games": 6,
                    "playedGames": 1,
                    "timeOnIce": 138,
                    "blockedOrSavedShots": 0,
                    "goalsAgainst": 0,
                    "savePercentage": None,
                    "goalsAgainstAvg": 0,
                    "gkWins": 0,
                    "gkLosses": 0,
                    "gkTies": 0,
                    "shutOut": 0,
                }
            ]
        ),
        encoding="utf-8",
    )

    enrich_europe_stats(
        base,
        output,
        [
            EuropeStatSource(
                "2024-25",
                "liiga",
                "Liiga",
                "https://example.test",
                kind="goalies",
                source_path=cache,
            )
        ],
    )

    rows = list(csv.DictReader((output / "season_stat_lines.csv").open(encoding="utf-8")))
    assert len(rows) == 3
    by_source = {row["source"]: row for row in rows}
    assert by_source["liiga"]["games"] == "1"
    assert by_source["liiga"]["goalie_minutes"] == "2.30"
    assert by_source["liiga; eliteprospects_pdf"]["games"] == "6"
    assert by_source["eliteprospects_pdf"]["games"] == "40"


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


def test_parse_khl_player_profile_preserves_stages_and_advanced_stats():
    raw = """
    <title>Жаровский Александр, хоккеист: статистика, матчи КХЛ, новости</title>
    <table><thead><tr><th>Турнир / Команда</th><th>№</th><th>И</th><th>Ш</th>
    <th>А</th><th>О</th><th>+/-</th><th>БВ</th><th>Вбр</th><th>ВВбр</th>
    <th>%Вбр</th><th>БлБ</th></tr></thead><tbody>
    <tr><td colspan="12">24/25 | Регулярный чемпионат</td></tr>
    <tr><td>Салават Юлаев</td><td>27</td><td>7</td><td>0</td><td>1</td><td>1</td>
    <td>2</td><td>8</td><td>20</td><td>9</td><td>45.0</td><td>3</td></tr>
    <tr><td colspan="12">24/25 | Плей-офф</td></tr>
    <tr><td>Салават Юлаев</td><td>27</td><td>3</td><td>1</td><td>0</td><td>1</td>
    <td>1</td><td>5</td><td>10</td><td>6</td><td>60.0</td><td>2</td></tr>
    </tbody></table>
    """

    lines = parse_khl_html(
        raw,
        EuropeStatSource(
            "2024-25", "khl", "KHL", "https://www.khl.ru/players/43001/", kind="profile"
        ),
    )

    assert [(line.season, line.regular_season, line.games) for line in lines] == [
        ("2024-25", True, "7"),
        ("2024-25", False, "3"),
    ]
    assert lines[0].name == "Александр Жаровский"
    assert lines[0].source_id == "43001"
    assert lines[0].points == "1"
    assert lines[0].blocks == "3"
    assert lines[0].faceoff_losses == "11"


def test_parse_mhl_goalie_profile_preserves_goalie_metrics():
    raw = """
    <title>Тулинов Никита, хоккеист: статистика, матчи МХЛ, новости</title>
    <table><thead><tr><th>Турнир / Клуб</th><th>№</th><th>И</th><th>В</th>
    <th>П</th><th>ИБ</th><th>БВ</th><th>ПШ</th><th>ОБ</th><th>%ОБ</th>
    <th>КН</th><th>Ш</th><th>А</th><th>И"0"</th><th>Штр</th><th>ВП</th>
    </tr></thead><tbody>
    <tr><td colspan="16">22/23 | Плей-офф</td></tr>
    <tr><td>Сибирские Снайперы</td><td>95</td><td>3</td><td>0</td><td>1</td>
    <td>0</td><td>65</td><td>9</td><td>56</td><td>86.2</td><td>5.19</td>
    <td>0</td><td>1</td><td>0</td><td>0</td><td>103:58</td></tr>
    </tbody></table>
    """

    lines = parse_khl_html(
        raw,
        EuropeStatSource(
            "2022-23", "khl", "MHL", "https://mhl.khl.ru/players/39262/", kind="profile"
        ),
    )

    assert len(lines) == 1
    assert lines[0].name == "Никита Тулинов"
    assert lines[0].regular_season is False
    assert lines[0].save_percentage == "0.862"
    assert lines[0].goals_against_average == "5.19"
    assert lines[0].shutouts == "0"


def test_enrichment_matches_within_country_family_and_writes_advanced_table(tmp_path):
    base = tmp_path / "base"
    output = tmp_path / "output"
    second_output = tmp_path / "second-output"
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
    enrich_europe_stats(
        output,
        second_output,
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
    second_advanced = list(
        csv.DictReader((second_output / "advanced_stat_lines.csv").open(encoding="utf-8"))
    )
    assert summary.matched_players == 1
    assert stats[0]["points"] == "45"
    assert stats[0]["source"] == "old"
    assert advanced[0]["games"] == "37"
    assert advanced[0]["plus_minus"] == "18"
    assert advanced[0]["source"] == "swehockey"
    assert len(second_advanced) == 1


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


def test_enrichment_marks_unavailable_provider_family_as_not_configured(tmp_path):
    base = tmp_path / "base"
    output = tmp_path / "output"
    base.mkdir()
    write_table(
        base / "players.csv",
        PLAYER_COLUMNS,
        [{"player_id": "p1", "name": "Russian Prospect", "position": "C", "source": "test"}],
    )
    write_table(
        base / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "p1",
                "season": "2023-24",
                "league": "MHL",
                "team": "Test",
                "timing": "pre_draft",
            }
        ],
    )
    cache = tmp_path / "sweden.html"
    cache.write_text(SWEHOCKEY_HTML, encoding="utf-8")

    enrich_europe_stats(
        base,
        output,
        [
            EuropeStatSource(
                "2023-24",
                "swehockey",
                "Sweden Jrs.",
                "https://example.test",
                source_path=cache,
            )
        ],
    )

    matches = list(csv.DictReader((output / "europe_stat_matches.csv").open(encoding="utf-8")))
    assert matches[0]["matched"] == "false"
    assert matches[0]["match_method"] == "not_configured"
