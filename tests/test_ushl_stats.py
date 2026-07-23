import csv
import json

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.ushl_stats import (
    UShlSkaterStatLine,
    UShlStatSource,
    competition_context,
    deduplicate_ushl_lines,
    enrich_ushl_stats,
    has_role_collision,
    is_usntdp_team,
    match_disposition,
    parse_ushl_goalies_json,
    parse_ushl_skaters_json,
    player_role,
    ushl_alias_key,
    ushl_person_key,
)


def ushl_payload(*rows):
    return json.dumps([{"sections": [{"title": "Skaters", "headers": {}, "data": list(rows)}]}])


ROW = {
    "prop": {},
    "row": {
        "name": "Vaclav Nestrasil",
        "player_id": "11589",
        "team_code": "MUS",
        "games_played": "61",
        "goals": "19",
        "assists": "23",
        "points": "42",
    },
}


def test_parse_ushl_skaters_json_extracts_core_stats():
    rows = parse_ushl_skaters_json(
        ushl_payload(ROW),
        UShlStatSource(season="2024-25", season_id="85", regular_season=True),
    )

    assert len(rows) == 1
    assert rows[0].name == "Vaclav Nestrasil"
    assert rows[0].source_id == "11589"
    assert rows[0].team == "MUS"
    assert rows[0].games == "61"
    assert rows[0].goals == "19"
    assert rows[0].assists == "23"
    assert rows[0].points == "42"
    assert rows[0].regular_season is True


def test_parse_ushl_skaters_json_excludes_goalie_rows():
    goalie = {
        "row": {
            **ROW["row"],
            "name": "Sample Goalie",
            "player_id": "9001",
            "position": "G",
        }
    }

    rows = parse_ushl_skaters_json(
        ushl_payload(ROW, goalie),
        UShlStatSource(season="2024-25", season_id="85", regular_season=True),
    )

    assert [row.name for row in rows] == ["Vaclav Nestrasil"]


def test_parse_ushl_goalies_json_extracts_role_specific_stats():
    row = {
        "row": {
            "name": "Sample Goalie",
            "player_id": "9001",
            "team_code": "USA",
            "games_played": "20",
            "minutes_played": 1100,
            "shots": "600",
            "goals_against": "48",
            "save_percentage": "0.920",
            "goals_against_average": "2.62",
            "wins": "12",
            "losses": "5",
            "ot_losses": "2",
            "shutouts": "3",
        }
    }

    rows = parse_ushl_goalies_json(
        ushl_payload(row),
        UShlStatSource(
            season="2024-25",
            season_id="85",
            regular_season=True,
            position="goalies",
        ),
    )

    assert rows[0].games == "20"
    assert rows[0].shots_against == "600"
    assert rows[0].saves == "552"
    assert rows[0].save_percentage == "0.920"
    assert rows[0].goals_against_average == "2.62"
    assert rows[0].ties == "2"
    assert rows[0].shutouts == "3"


def test_enrich_ushl_stats_replaces_matching_placeholder_rows(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "ushl.json"
    base_dir.mkdir()
    source_path.write_text(ushl_payload(ROW), encoding="utf-8")
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-025-vaclav-nestrasil",
                "name": "Vaclav Nestrasil",
                "birth_date": "",
                "nationality": "Czechia",
                "position": "RW",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-025-vaclav-nestrasil",
                "source_url": "",
            },
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-025-vaclav-nestrasil",
                "season": "2024-25",
                "league": "USHL",
                "team": "Muskegon Lumberjacks",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-025-vaclav-nestrasil",
                "source_url": "",
            },
            {
                "player_id": "2025-025-vaclav-nestrasil",
                "season": "2024-25",
                "league": "USHL",
                "team": "USA U-18",
                "games": "4",
                "goals": "1",
                "assists": "2",
                "points": "3",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "curated",
                "source_id": "ntdp-context",
                "source_url": "",
            },
            {
                "player_id": "2025-025-vaclav-nestrasil",
                "season": "2023-24",
                "league": "USHL",
                "team": "Muskegon Lumberjacks",
                "games": "3",
                "goals": "1",
                "assists": "1",
                "points": "2",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "false",
                "source": "curated",
                "source_id": "historical-playoff",
                "source_url": "",
            },
        ],
    )

    summary = enrich_ushl_stats(
        base_dir,
        output_dir,
        [
            UShlStatSource(
                season="2024-25",
                season_id="85",
                regular_season=True,
                source_path=source_path,
            )
        ],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))
    with (output_dir / "ushl_stat_matches.csv").open(newline="", encoding="utf-8") as file:
        matches = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 3
    official = next(row for row in stat_lines if row["source"] == "ushl")
    ntdp = next(row for row in stat_lines if row["source_id"] == "ntdp-context")
    historical = next(row for row in stat_lines if row["season"] == "2023-24")
    assert official["source"] == "ushl"
    assert official["games"] == "61"
    assert official["points"] == "42"
    assert ntdp["team"] == "USA U-18"
    assert historical["source"] == "curated"
    assert historical["regular_season"] == "false"
    assert matches[0]["matched"] == "true"
    assert matches[0]["disposition"] == "matched"
    assert matches[0]["source_availability"] == "available"
    assert matches[0]["competition_context"] == "ushl_club"
    assert summary.disposition_counts == {"matched": 1}


def test_ushl_match_dispositions_are_explicit():
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


def test_ushl_parser_preserves_playoff_and_ntdp_team_flags():
    ntdp_row = {"row": {**ROW["row"], "team_code": "USA"}}

    lines = parse_ushl_skaters_json(
        ushl_payload(ntdp_row),
        UShlStatSource(
            season="2024-25",
            season_id="87",
            regular_season=False,
        ),
    )

    assert lines[0].team == "USA"
    assert lines[0].regular_season is False


def test_ushl_person_key_ignores_common_name_suffixes():
    assert ushl_person_key("Drew Schock IV") == ushl_person_key("Drew Schock")
    assert ushl_person_key("Example Player, Jr.") == ushl_person_key("Example Player")


def test_ushl_alias_key_maps_common_first_name_variants():
    assert ushl_alias_key("Will Moore") == ushl_alias_key("William Moore")


def test_usntdp_team_context_uses_reviewed_team_labels():
    assert is_usntdp_team("U.S. NTDP")
    assert is_usntdp_team("NTDP")
    assert is_usntdp_team("USA U-18")
    assert is_usntdp_team("U.S. National Under-18 Team")
    assert competition_context("USA") == "usntdp"
    assert competition_context("MUS") == "ushl_club"
    assert player_role("G") == "goalie"
    assert player_role("RW") == "skater"


def test_ushl_candidate_deduplication_and_role_collision():
    skater = UShlSkaterStatLine(
        "Example Player",
        "100",
        "",
        "2024-25",
        "USA",
        "10",
        "2",
        "3",
        "5",
        True,
    )
    goalie = UShlSkaterStatLine(
        "Example Player",
        "100",
        "",
        "2024-25",
        "USA",
        "10",
        "",
        "",
        "",
        True,
        save_percentage="0.920",
    )

    assert deduplicate_ushl_lines([skater, skater]) == [skater]
    assert has_role_collision([skater, goalie])
    assert (
        match_disposition(
            eligible=True,
            name_count=1,
            has_candidates=True,
            role_collision=True,
            source_availability="available",
        )
        == "ambiguous_identity"
    )
    assert (
        match_disposition(
            eligible=True,
            name_count=1,
            has_candidates=True,
            team_mismatch=True,
            source_availability="available",
        )
        == "usntdp_team_mismatch"
    )
