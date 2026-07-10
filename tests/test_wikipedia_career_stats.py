import csv
import json

from draft_room_intelligence.data.eliteprospects_csv import PLAYER_COLUMNS, SEASON_STAT_LINE_COLUMNS, write_table
from draft_room_intelligence.data.wikipedia_career_stats import (
    enrich_wikipedia_career_stats,
    parse_career_stat_lines,
)


WIKITEXT = """
==Career statistics==
===Regular season and playoffs===
{| border="0" cellpadding="1" cellspacing="0"
|- bgcolor="#e0e0e0"
! Season
! Team
! League
! GP !! G !! A !! Pts !! PIM
! GP !! G !! A !! Pts !! PIM
|-
| [[2024–25 HockeyAllsvenskan season|2024–25]]
| [[Djurgårdens IF (men's ice hockey)|Djurgårdens IF]]
| [[HockeyAllsvenskan|Allsv]]
| 29 || 11 || 14 || 25 || 16
| 16 || 3 || 4 || 7 || 4
|- bgcolor="#e0e0e0"
! colspan="3"|SHL totals
! 1 !! 0 !! 0 !! 0 !! 0
! — !! — !! — !! — !! —
|}
"""


ZHAROVSKY_WIKITEXT = """
==Career statistics==
{| border="0" cellpadding="1" cellspacing="0"
! Season
! Team
! League
! GP !! G !! A !! Pts !! PIM
! GP !! G !! A !! Pts !! PIM
|-
| 2024–25
| [[Tolpar Ufa]]
| [[Junior Hockey League (Russia)|MHL]]
| 45 || 24 || 26 || 50 || 30
| – || – || – || – || –
|- bgcolor="#f0f0f0"
| [[2024–25 KHL season|2024–25]]
| [[Salavat Yulaev Ufa]]
| [[Kontinental Hockey League|KHL]]
| – || – || – || – || –
| 7 || 0 || 1 || 1 || 2
|}
"""


def test_parse_career_stat_lines_extracts_regular_and_playoffs():
    rows = parse_career_stat_lines(
        WIKITEXT,
        {
            "player_id": "2025-003-anton-frondell",
            "name": "Anton Frondell",
            "title": "Anton Frondell",
            "source_url": "https://en.wikipedia.org/wiki/Anton_Frondell",
        },
        season="2024-25",
    )

    assert len(rows) == 2
    assert rows[0].league == "Allsv"
    assert rows[0].team == "Djurgårdens IF"
    assert rows[0].games == "29"
    assert rows[0].points == "25"
    assert rows[0].regular_season is True
    assert rows[1].games == "16"
    assert rows[1].points == "7"
    assert rows[1].regular_season is False


def test_enrich_wikipedia_career_stats_replaces_matching_placeholder(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    base_dir.mkdir()
    cache_dir.mkdir()
    (cache_dir / "antonfrondell.json").write_text(
        json.dumps({"title": "Anton Frondell", "wikitext": WIKITEXT}),
        encoding="utf-8",
    )
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-003-anton-frondell",
                "name": "Anton Frondell",
                "birth_date": "",
                "nationality": "Sweden",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-003-anton-frondell",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-003-anton-frondell",
                "season": "2024-25",
                "league": "Swe-1",
                "team": "Djurgardens IF",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-003-anton-frondell",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "wikipedia_bio_matches.csv",
        [
            "player_id",
            "name",
            "matched",
            "title",
            "wikidata_id",
            "source_url",
            "birth_date",
            "height_cm",
            "weight_kg",
            "handedness",
            "position",
        ],
        [
            {
                "player_id": "2025-003-anton-frondell",
                "name": "Anton Frondell",
                "matched": "true",
                "title": "Anton Frondell",
                "wikidata_id": "",
                "source_url": "https://en.wikipedia.org/wiki/Anton_Frondell",
                "birth_date": "",
                "height_cm": "",
                "weight_kg": "",
                "handedness": "",
                "position": "",
            }
        ],
    )

    summary = enrich_wikipedia_career_stats(base_dir, output_dir, season="2024-25", cache_dir=cache_dir)

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 2
    assert {row["regular_season"] for row in stat_lines} == {"true", "false"}
    assert stat_lines[0]["source"] == "wikipedia-career"
    assert stat_lines[0]["league"] == "Swe-1"


def test_enrich_wikipedia_career_stats_appends_additional_same_season_leagues(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    cache_dir = tmp_path / "cache"
    base_dir.mkdir()
    cache_dir.mkdir()
    (cache_dir / "alexanderzharovsky.json").write_text(
        json.dumps({"title": "Alexander Zharovsky", "wikitext": ZHAROVSKY_WIKITEXT}),
        encoding="utf-8",
    )
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-034-alexander-zharovsky",
                "name": "Alexander Zharovsky",
                "birth_date": "",
                "nationality": "Russia",
                "position": "R",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-034-alexander-zharovsky",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-034-alexander-zharovsky",
                "season": "2024-25",
                "league": "Rus-MHL",
                "team": "Tolpar Ufa",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-034-alexander-zharovsky",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "wikipedia_bio_matches.csv",
        [
            "player_id",
            "name",
            "matched",
            "title",
            "wikidata_id",
            "source_url",
            "birth_date",
            "height_cm",
            "weight_kg",
            "handedness",
            "position",
        ],
        [
            {
                "player_id": "2025-034-alexander-zharovsky",
                "name": "Alexander Zharovsky",
                "matched": "true",
                "title": "Alexander Zharovsky",
                "wikidata_id": "",
                "source_url": "https://en.wikipedia.org/wiki/Alexander_Zharovsky",
                "birth_date": "",
                "height_cm": "",
                "weight_kg": "",
                "handedness": "",
                "position": "",
            }
        ],
    )

    summary = enrich_wikipedia_career_stats(base_dir, output_dir, season="2024-25", cache_dir=cache_dir)

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 2
    assert {(row["league"], row["regular_season"]) for row in stat_lines} == {
        ("Rus-MHL", "true"),
        ("KHL", "false"),
    }
    playoff_row = [row for row in stat_lines if row["league"] == "KHL"][0]
    assert playoff_row["team"] == "Salavat Yulaev Ufa"
    assert playoff_row["games"] == "7"
    assert playoff_row["points"] == "1"
