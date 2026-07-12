from draft_room_intelligence.data.eliteprospects_pdf import normalize_eliteprospects_pdf_pages
from draft_room_intelligence.data.eliteprospects_pdf import parse_player_index_rows
from draft_room_intelligence.data.eliteprospects_pdf import parse_tool_grade_json
from draft_room_intelligence.data.eliteprospects_pdf import parse_profile_page
from draft_room_intelligence.data.eliteprospects_pdf import enrich_missing_tool_grades_with_vision
from draft_room_intelligence.data.eliteprospects_pdf import apply_index_rows
from draft_room_intelligence.data.eliteprospects_pdf import tool_grade_prompt


DRAFT25_PROFILE = """NHL DRAFT GUIDE 2025
How can a player who only suited up for 26 games be ranked first overall?
D|Matthew Schaefer
Elevator Pitch
An overwhelmingly skilled and dynamic play-driving talent
with unmatched developmental runway.
Tool Grades (1.0 to 9.0)
8.0 7. 0 7. 5 7. 0 7. 5 6.0 A
Skating Shooting Passing Handling Sense Physical Grade
Prospect Profile
183 lbs L6'1.75" 2007-09-05
Engine Fleet of Foot Transition
Ace
1
Shades of... Miro Heiskanen
Team League GP G A P G/GP A/GP P/GP
Erie Otters OHL 17 7 15 22 0.41 0.88 1.29
Canada U20 WJC-20 2 1 1 2 0.50 0.50 1.00
Range: 1 - 2
"""


DRAFT26_PROFILE = """Gavin McKenna SHADES OF... Patrick Kane, Nikita Kucherov1
TOOL GRADES (1-TO-9)
2025-26 STATISTICS
Penn State Univ. (NCAA) 35 15 36 51 .43 1.03 1.46
Canada U20 (WJC-20) 7 4 10 14 .57 1.43 2.00
TEAM (LEAGUE) GP G A PTS G/GP A/GP PTS/GP
Chess master
A
BADGES
GRADE
HEIGHT
5'11" 170 lbs
WEIGHT
Left 2007-12-20
SHOOTS DATE OF BIRTH
LW
POSITION(S)
Usually, when a prospect draws comparison to Patrick Kane or Nikita Kucherov,
those parallels simply describe the general playstyle of a prospect.
SKATING
HANDLING
Vision
Tactician
PROSPECT PROFILE
NHL DRAFT GUIDE 2026
PROSPECT SUMMARY
Playmaking wizard, combining elite deception, timing, and skill to break down defences with ease.
SHOOTING
SENSE
PASSING
PHYSICAL
RANK RANGE
1 - 3
"""


DRAFT26_GOALIE_PROFILE = """Tobias Trejbal SHADES OF... A more athletic Dan Vladar34
TOOL GRADES (1-TO-9)
2025-26 STATISTICS
Youngstown Phantoms (USHL) 41 2.15 .915 3
TEAM (LEAGUE) GP GAA SV% SO
Precise
B
BADGES
GRADE
HEIGHT
6'3.75" 188 lbs
WEIGHT
Right 2007-11-09
CATCHES DATE OF BIRTH
G
POSITION(S)
SKATING
ATHLETICISM
TRANSITIONS
POSITIONING
PLAY READING
TECHNIQUE
RANK RANGE
30 - 45
"""


def test_parse_2025_profile_extracts_bio_stats_ranking_and_tools():
    profile = parse_profile_page(
        DRAFT25_PROFILE,
        draft_year=2025,
        page_number=29,
        source_name="Draft25.pdf",
    )

    assert profile is not None
    assert profile.name == "Matthew Schaefer"
    assert profile.player_id == "2025-ep-matthew-schaefer"
    assert profile.position == "D"
    assert profile.handedness == "L"
    assert profile.height_cm == "187"
    assert profile.weight_kg == "83"
    assert profile.birth_date == "2007-09-05"
    assert profile.rank == "1"
    assert profile.rank_range == "1 - 2"
    assert profile.grade == "A"
    assert profile.shades_of == "Miro Heiskanen"
    assert profile.badges == ("Ace", "Engine Fleet of Foot Transition")
    assert len(profile.stat_lines) == 2
    assert profile.stat_lines[0]["league"] == "OHL"
    assert profile.stat_lines[0]["points"] == "22"
    assert profile.tool_grades[0]["tool"] == "skating"
    assert profile.tool_grades[0]["grade"] == "8.0"


def test_parse_2026_profile_extracts_layout_variant_without_tool_grades():
    profile = parse_profile_page(
        DRAFT26_PROFILE,
        draft_year=2026,
        page_number=36,
        source_name="Draft26.pdf",
    )

    assert profile is not None
    assert profile.name == "Gavin McKenna"
    assert profile.position == "LW"
    assert profile.handedness == "L"
    assert profile.height_cm == "180"
    assert profile.weight_kg == "77"
    assert profile.birth_date == "2007-12-20"
    assert profile.rank == "1"
    assert profile.rank_range == "1 - 3"
    assert profile.grade == "A"
    assert profile.shades_of == "Patrick Kane, Nikita Kucherov"
    assert "Chess master" in profile.badges
    assert "Vision" in profile.badges
    assert len(profile.stat_lines) == 2
    assert profile.stat_lines[0]["league"] == "NCAA"
    assert profile.stat_lines[0]["season"] == "2025-26"
    assert "missing_tool_grades" in profile.extraction_warnings


def test_parse_2026_goalie_profile_extracts_goalie_stats():
    profile = parse_profile_page(
        DRAFT26_GOALIE_PROFILE,
        draft_year=2026,
        page_number=122,
        source_name="Draft26.pdf",
    )

    assert profile is not None
    assert profile.position == "G"
    assert profile.stat_lines[0]["league"] == "USHL"
    assert profile.stat_lines[0]["goals"] == ""
    assert profile.stat_lines[0]["goals_against_average"] == "2.15"
    assert profile.stat_lines[0]["save_percentage"] == "0.915"
    assert profile.stat_lines[0]["shutouts"] == "3"
    assert "missing_stat_lines" not in profile.extraction_warnings


def test_normalize_pdf_pages_writes_normalized_export_shape():
    export = normalize_eliteprospects_pdf_pages(
        [(29, DRAFT25_PROFILE), (36, DRAFT26_PROFILE)],
        draft_year=2025,
        source_name="Draft25.pdf",
    )

    assert len(export.players) == 2
    assert len(export.season_stat_lines) == 4
    assert len(export.rankings) == 2
    assert len(export.profile_rows) == 2
    assert export.players[0]["source"] == "eliteprospects_pdf"
    assert export.profile_rows[0]["source_url"] == "Draft25.pdf#page=29"


def test_parse_tool_grade_json_normalizes_model_output():
    grades = parse_tool_grade_json(
        '{"skating": "6.5", "shooting": 6, "passing": "8.5", "ignored": "9.0"}'
    )

    assert grades == {
        "skating": "6.5",
        "shooting": "6.0",
        "passing": "8.5",
    }


def test_parse_goalie_tool_grade_json_uses_goalie_labels():
    grades = parse_tool_grade_json(
        '{"skating": "6.5", "athleticism": "6.5", "transitions": "6.5", '
        '"positioning": 6, "play_reading": "4.5", "technique": "6.5", '
        '"shooting": "9.0"}',
        allowed_tools=[
            "skating",
            "athleticism",
            "transitions",
            "positioning",
            "play_reading",
            "technique",
        ],
    )

    assert grades == {
        "skating": "6.5",
        "athleticism": "6.5",
        "transitions": "6.5",
        "positioning": "6.0",
        "play_reading": "4.5",
        "technique": "6.5",
    }


def test_player_index_rows_backfill_missing_profile_rank():
    profile_text = DRAFT25_PROFILE.replace("\n1\nShades of", "\nShades of")
    export = normalize_eliteprospects_pdf_pages(
        [(29, profile_text)],
        draft_year=2025,
        source_name="Draft25.pdf",
    )
    index_rows = parse_player_index_rows(
        [
            (
                5,
                "NHL DRAFT GUIDE 2025\n"
                "1 Matthew Schaefer, D Erie Otters (OHL) A Grade 29\n"
                "Player Index: Ranked Prospects",
            )
        ],
        draft_year=2025,
        source_name="Draft25.pdf",
    )

    enriched = apply_index_rows(export, index_rows)

    assert index_rows[0]["league"] == "OHL"
    assert enriched.profiles[0].rank == "1"
    assert enriched.rankings[0]["rank"] == "1"
    assert enriched.index_rows[0]["profile_page"] == "29"


def test_player_index_rows_supply_missing_profile_identity():
    index_rows = parse_player_index_rows(
        [
            (
                6,
                "46 Mason West, C/RW Edina High (USHS-MN) B Grade 568",
            )
        ],
        draft_year=2025,
        source_name="Draft25.pdf",
    )
    text_without_sidebar_name = DRAFT25_PROFILE.replace("D|Matthew Schaefer", "Mason West")

    export = normalize_eliteprospects_pdf_pages(
        [(568, text_without_sidebar_name)],
        draft_year=2025,
        source_name="Draft25.pdf",
        index_rows=index_rows,
    )

    assert export.profiles[0].name == "Mason West"
    assert export.profiles[0].rank == "46"
    assert export.profiles[0].position == "CRW"


def test_vision_enrichment_fills_missing_tool_grades_with_mock_client(tmp_path):
    class FakeVisionClient:
        model = "fake-vision"
        last_usage = {"input_tokens": "100", "output_tokens": "20", "total_tokens": "120"}

        def extract_tool_grades(self, image_path, profile):
            assert image_path.exists()
            assert profile.name == "Gavin McKenna"
            return {
                "skating": "6.5",
                "shooting": "6.5",
                "passing": "8.5",
                "handling": "8.5",
                "sense": "8.5",
                "physical": "4",
            }

    fake_pdftoppm = tmp_path / "pdftoppm"
    fake_pdftoppm.write_text(
        "#!/bin/sh\n"
        "for arg do prefix=\"$arg\"; done\n"
        "printf 'png' > \"$prefix.png\"\n",
        encoding="utf-8",
    )
    fake_pdftoppm.chmod(0o755)
    export = normalize_eliteprospects_pdf_pages(
        [(36, DRAFT26_PROFILE)],
        draft_year=2026,
        source_name="Draft26.pdf",
    )

    enriched = enrich_missing_tool_grades_with_vision(
        tmp_path / "Draft26.pdf",
        tmp_path / "vision_pages",
        export,
        pdftoppm_path=fake_pdftoppm,
        vision_client=FakeVisionClient(),
    )

    assert len(enriched.tool_grade_rows) == 6
    assert enriched.tool_grade_rows[0]["source"] == "eliteprospects_pdf_vision"
    assert enriched.tool_grade_rows[-1]["grade"] == "4.0"
    assert enriched.vision_usage_rows[0]["model"] == "fake-vision"
    assert enriched.vision_usage_rows[0]["total_tokens"] == "120"
    assert "tool_grades_from_vision" in enriched.profiles[0].extraction_warnings
    assert "missing_tool_grades" not in enriched.profiles[0].extraction_warnings


def test_goalie_vision_prompt_uses_goalie_tool_labels():
    profile = parse_profile_page(
        DRAFT26_PROFILE.replace("LW\nPOSITION(S)", "G\nPOSITION(S)"),
        draft_year=2026,
        page_number=122,
        source_name="Draft26.pdf",
    )

    assert profile is not None
    prompt = tool_grade_prompt(profile)
    assert "goalie profile" in prompt
    assert "athleticism" in prompt
    assert "play_reading" in prompt
