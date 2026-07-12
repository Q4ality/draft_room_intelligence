from draft_room_intelligence.data.eliteprospects_pdf import normalize_eliteprospects_pdf_pages
from draft_room_intelligence.data.eliteprospects_pdf import parse_tool_grade_json
from draft_room_intelligence.data.eliteprospects_pdf import parse_profile_page
from draft_room_intelligence.data.eliteprospects_pdf import enrich_missing_tool_grades_with_vision


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


def test_vision_enrichment_fills_missing_tool_grades_with_mock_client(tmp_path):
    class FakeVisionClient:
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
    assert "tool_grades_from_vision" in enriched.profiles[0].extraction_warnings
    assert "missing_tool_grades" not in enriched.profiles[0].extraction_warnings
