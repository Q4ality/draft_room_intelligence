import csv

from draft_room_intelligence.data.ep_pdf_overlay import overlay_ep_pdf_demo_dataset


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_overlay_ep_pdf_demo_dataset_remaps_sidecars_and_dedupes_stats(tmp_path):
    base = tmp_path / "base"
    source = tmp_path / "ep"
    output = tmp_path / "out"
    player_columns = [
        "player_id",
        "name",
        "birth_date",
        "nationality",
        "position",
        "handedness",
        "height_cm",
        "weight_kg",
        "age_at_draft",
        "source",
        "source_id",
        "source_url",
    ]
    stat_columns = [
        "player_id",
        "season",
        "league",
        "team",
        "games",
        "goals",
        "assists",
        "points",
        "age",
        "timing",
        "regular_season",
        "source",
        "source_id",
        "source_url",
        "goalie_minutes",
        "shots_against",
        "saves",
        "goals_against",
        "save_percentage",
        "goals_against_average",
        "wins",
        "losses",
        "ties",
        "shutouts",
    ]
    ranking_columns = [
        "player_id",
        "draft_year",
        "source",
        "rank",
        "scope",
        "position",
        "source_id",
        "source_url",
    ]
    profile_columns = [
        "player_id",
        "draft_year",
        "name",
        "page_start",
        "page_end",
        "rank",
        "rank_range",
        "grade",
        "position",
        "handedness",
        "height_text",
        "height_cm",
        "weight_kg",
        "birth_date",
        "shades_of",
        "badges",
        "profile_summary",
        "profile_text_chars",
        "extraction_warnings",
        "source",
        "source_id",
        "source_url",
    ]
    tool_columns = ["player_id", "tool", "grade", "source", "source_id", "source_url"]

    write_csv(
        base / "players.csv",
        player_columns,
        [
            {
                "player_id": "base-joshua",
                "name": "Joshua Ravensbergen",
                "birth_date": "",
                "nationality": "CAN",
                "position": "G",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "18",
                "source": "wikipedia",
                "source_id": "",
                "source_url": "",
            }
        ],
    )
    write_csv(
        base / "season_stat_lines.csv",
        stat_columns,
        [
            {
                "player_id": "base-joshua",
                "season": "2024-25",
                "league": "WHL",
                "team": "Prince George Cougars",
                "games": "51",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "",
                "source_url": "",
                "goalie_minutes": "",
                "shots_against": "",
                "saves": "",
                "goals_against": "",
                "save_percentage": "",
                "goals_against_average": "",
                "wins": "",
                "losses": "",
                "ties": "",
                "shutouts": "",
            }
        ],
    )
    write_csv(base / "rankings.csv", ranking_columns, [])
    write_csv(base / "draft_selections.csv", ["player_id"], [{"player_id": "base-joshua"}])
    write_csv(base / "nhl_outcomes.csv", ["player_id"], [{"player_id": "base-joshua"}])

    write_csv(
        source / "players.csv",
        player_columns,
        [
            {
                "player_id": "ep-joshua",
                "name": "Joshua Ravensbergen",
                "birth_date": "2006-11-27",
                "nationality": "",
                "position": "G",
                "handedness": "R",
                "height_cm": "196",
                "weight_kg": "86",
                "age_at_draft": "",
                "source": "eliteprospects_pdf",
                "source_id": "2025-ep-pdf-page-364",
                "source_url": "Draft25.pdf#page=364",
            }
        ],
    )
    write_csv(
        source / "season_stat_lines.csv",
        stat_columns,
        [
            {
                "player_id": "ep-joshua",
                "season": "2024-25",
                "league": "WHL",
                "team": "Prince George Cougars",
                "games": "51",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "eliteprospects_pdf",
                "source_id": "2025-ep-pdf-page-364",
                "source_url": "Draft25.pdf#page=364",
                "goalie_minutes": "",
                "shots_against": "",
                "saves": "",
                "goals_against": "",
                "save_percentage": ".901",
                "goals_against_average": "3.00",
                "wins": "",
                "losses": "",
                "ties": "",
                "shutouts": "0",
            }
        ],
    )
    write_csv(source / "rankings.csv", ranking_columns, [])
    write_csv(
        source / "ep_pdf_profiles.csv",
        profile_columns,
        [
            {
                "player_id": "ep-joshua",
                "draft_year": "2025",
                "name": "Joshua Ravensbergen",
                "page_start": "364",
                "page_end": "364",
                "rank": "24",
                "rank_range": "23 - 34",
                "grade": "A",
                "position": "G",
                "handedness": "R",
                "height_text": "6'5.25",
                "height_cm": "196",
                "weight_kg": "86",
                "birth_date": "2006-11-27",
                "shades_of": "Ben Bishop",
                "badges": "Composed",
                "profile_summary": "Big confident goalie.",
                "profile_text_chars": "100",
                "extraction_warnings": "",
                "source": "eliteprospects_pdf",
                "source_id": "2025-ep-pdf-page-364",
                "source_url": "Draft25.pdf#page=364",
            }
        ],
    )
    write_csv(
        source / "ep_pdf_tool_grades.csv",
        tool_columns,
        [
            {
                "player_id": "ep-joshua",
                "tool": "depth",
                "grade": "7.0",
                "source": "eliteprospects_pdf_vision",
                "source_id": "2025-ep-pdf-page-364",
                "source_url": "Draft25.pdf#page=364",
            }
        ],
    )

    summary = overlay_ep_pdf_demo_dataset(base, source, output)

    assert summary.matched_players == 1
    assert summary.added_stat_lines == 0
    assert summary.augmented_stat_lines == 1
    stats = list(csv.DictReader((output / "season_stat_lines.csv").open()))
    assert stats[0]["player_id"] == "base-joshua"
    assert stats[0]["save_percentage"] == ".901"
    profiles = list(csv.DictReader((output / "ep_pdf_profiles.csv").open()))
    grades = list(csv.DictReader((output / "ep_pdf_tool_grades.csv").open()))
    assert profiles[0]["player_id"] == "base-joshua"
    assert grades[0]["player_id"] == "base-joshua"
