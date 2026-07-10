from draft_room_intelligence.data.puckpedia_stats import parse_puckpedia_stat_lines
from draft_room_intelligence.data.puckpedia_stats import slugify_player_name


PUCKPEDIA_HTML = """
<html>
  <body>
    <div>2024-25 18 WJAC-19 USA U19 5 2 5 7 0</div>
    <div>2024-25 18 USHL Waterloo Black Hawks 58 24 18 42 4 Playoffs 15 7 7 14 0</div>
    <div>2023-24 17 NTDP U.S. National U18 Team 61 8 14 22 18</div>
  </body>
</html>
"""


def test_parse_puckpedia_stat_lines_extracts_regular_playoff_and_tournament_rows():
    rows = parse_puckpedia_stat_lines(
        PUCKPEDIA_HTML,
        "Brendan McMorrow",
        "brendan-mcmorrow",
        "https://puckpedia.com/player/brendan-mcmorrow",
        season="2024-25",
    )

    assert len(rows) == 3
    assert [(row.league, row.team, row.games, row.points, row.regular_season) for row in rows] == [
        ("WJAC-19", "USA U19", "5", "7", True),
        ("USHL", "Waterloo Black Hawks", "58", "42", True),
        ("USHL", "Waterloo Black Hawks", "15", "14", False),
    ]


def test_slugify_player_name_matches_puckpedia_shape():
    assert slugify_player_name("Brendan McMorrow") == "brendan-mcmorrow"
    assert slugify_player_name("Jake O'Brien") == "jake-obrien"
