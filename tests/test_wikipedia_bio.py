import csv

from draft_room_intelligence.data.eliteprospects_csv import PLAYER_COLUMNS, SEASON_STAT_LINE_COLUMNS, write_table
from draft_room_intelligence.data.wikipedia_bio import (
    WikipediaBio,
    enrich_wikipedia_bios,
    parse_infobox_bio,
)


def test_parse_infobox_bio_extracts_public_bio_fields():
    wikitext = """
{{Infobox ice hockey player
| name = Michael Misa
| birth_date = {{birth date and age|2007|2|16}}
| height_ft = 6
| height_in = 1
| weight_lb = 185
| position = [[Centre (ice hockey)|Centre]]
| shoots = Left
}}
"""

    bio = parse_infobox_bio(wikitext)

    assert bio["birth_date"] == "2007-02-16"
    assert bio["height_cm"] == "185"
    assert bio["weight_kg"] == "84"
    assert bio["position"] == "C"
    assert bio["handedness"] == "L"


def test_enrich_wikipedia_bios_updates_player_table_and_copies_dataset(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "enriched"
    base_dir.mkdir()
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
                "source_url": "https://en.wikipedia.org/wiki/2025_NHL_entry_draft",
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
                "source_url": "https://en.wikipedia.org/wiki/2025_NHL_entry_draft",
            }
        ],
    )

    def fake_fetcher(name):
        assert name == "Michael Misa"
        return WikipediaBio(
            title="Michael Misa",
            wikidata_id="Q120143115",
            source_url="https://en.wikipedia.org/wiki/Michael_Misa",
            birth_date="2007-02-16",
            height_cm="185",
            weight_kg="84",
            handedness="L",
            position="C",
        )

    summary = enrich_wikipedia_bios(base_dir, output_dir, fetcher=fake_fetcher)

    with (output_dir / "players.csv").open(newline="", encoding="utf-8") as file:
        players = list(csv.DictReader(file))
    with (output_dir / "wikipedia_bio_matches.csv").open(newline="", encoding="utf-8") as file:
        matches = list(csv.DictReader(file))

    assert summary.players_scanned == 1
    assert summary.matched_pages == 1
    assert summary.players_updated == 1
    assert players[0]["birth_date"] == "2007-02-16"
    assert players[0]["height_cm"] == "185"
    assert players[0]["weight_kg"] == "84"
    assert players[0]["handedness"] == "L"
    assert players[0]["source"] == "wikipedia+wikipedia_bio"
    assert players[0]["source_id"] == "Q120143115"
    assert matches[0]["matched"] == "true"
    assert (output_dir / "season_stat_lines.csv").exists()
