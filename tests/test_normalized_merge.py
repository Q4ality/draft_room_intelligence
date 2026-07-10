import csv

from draft_room_intelligence.data.merge_quality import (
    build_merge_quality_report,
    format_merge_quality_report,
)
from draft_room_intelligence.data.normalized_merge import merge_normalized_source_tables
from draft_room_intelligence.data.normalized_merge import generate_match_map_template


def test_merge_normalized_source_tables_replaces_matched_pre_draft_lines(tmp_path):
    base_dir = tmp_path / "base"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "merged"
    base_dir.mkdir()
    source_dir.mkdir()

    write_rows(
        base_dir / "players.csv",
        [
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
        ],
        [
            {
                "player_id": "2019-005-alex-turcotte",
                "name": "Alex Turcotte",
                "birth_date": "",
                "nationality": "",
                "position": "C",
                "handedness": "L",
                "height_cm": "180",
                "weight_kg": "88",
                "age_at_draft": "18.31",
                "source": "hockeydb",
                "source_id": "2019-005-alex-turcotte",
                "source_url": "https://example.test/hockeydb",
            },
            {
                "player_id": "2019-999-base-only",
                "name": "Base Only",
                "birth_date": "",
                "nationality": "",
                "position": "D",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "hockeydb",
                "source_id": "2019-999-base-only",
                "source_url": "",
            },
        ],
    )
    write_rows(
        base_dir / "season_stat_lines.csv",
        stat_columns(),
        [
            stat_row("2019-005-alex-turcotte", "USHL", "hockeydb", points="20"),
            stat_row("2019-999-base-only", "WHL", "hockeydb", points="10"),
        ],
    )
    write_rows(
        base_dir / "draft_selections.csv",
        ["player_id", "draft_year", "team_id", "team_name", "round_number", "overall_pick"],
        [
            {
                "player_id": "2019-005-alex-turcotte",
                "draft_year": "2019",
                "team_id": "LAK",
                "team_name": "Los Angeles",
                "round_number": "1",
                "overall_pick": "5",
            }
        ],
    )
    write_rows(
        source_dir / "players.csv",
        [
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
        ],
        [
            {
                "player_id": "2019-ep-209490",
                "name": "Alex Turcotte",
                "birth_date": "2001-02-26",
                "nationality": "USA",
                "position": "C",
                "handedness": "L",
                "height_cm": "180",
                "weight_kg": "88",
                "age_at_draft": "18.31",
                "source": "eliteprospects",
                "source_id": "209490",
                "source_url": "https://example.test/ep",
            },
            {
                "player_id": "2019-ep-unmatched",
                "name": "Unmatched Player",
                "birth_date": "",
                "nationality": "",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "eliteprospects",
                "source_id": "unmatched",
                "source_url": "",
            },
        ],
    )
    write_rows(
        source_dir / "season_stat_lines.csv",
        stat_columns(),
        [
            stat_row("2019-ep-209490", "USDP", "eliteprospects", points="62"),
            stat_row("2019-ep-unmatched", "OHL", "eliteprospects", points="99"),
        ],
    )

    summary = merge_normalized_source_tables(
        base_dir,
        source_dir,
        output_dir,
        source_name="eliteprospects",
    )

    merged_players = read_rows(output_dir / "players.csv")
    merged_stats = read_rows(output_dir / "season_stat_lines.csv")
    unmatched = read_rows(output_dir / "unmatched_source_players.csv")

    assert summary.matched_players == 1
    assert summary.manual_matches == 0
    assert summary.name_matches == 1
    assert summary.unmatched_source_players == 1
    assert merged_players[0]["player_id"] == "2019-005-alex-turcotte"
    assert merged_players[0]["source"] == "eliteprospects"
    assert merged_players[0]["source_id"] == "209490"
    assert merged_stats[0]["player_id"] == "2019-005-alex-turcotte"
    assert merged_stats[0]["league"] == "USDP"
    assert merged_stats[0]["points"] == "62"
    assert all(row["points"] != "20" for row in merged_stats)
    assert any(row["player_id"] == "2019-999-base-only" for row in merged_stats)
    assert unmatched[0]["name"] == "Unmatched Player"
    assert (output_dir / "draft_selections.csv").exists()

    quality = build_merge_quality_report(base_dir, source_dir, output_dir)

    assert quality.base_players == 2
    assert quality.source_players == 2
    assert quality.merged_players == 2
    assert quality.matched_source_players == 1
    assert quality.unmatched_source_players == 1
    assert quality.matched_rate == 0.5
    assert quality.replaced_pre_draft_players == 1
    assert quality.source_stat_lines_used == 1
    assert quality.duplicate_stat_lines == 0
    assert quality.missing_games == 0
    assert quality.missing_points == 0
    assert quality.added_leagues == ("USDP",)
    assert "matched_rate: 0.500" in format_merge_quality_report(quality)


def test_merge_normalized_source_tables_uses_manual_match_map(tmp_path):
    base_dir = tmp_path / "base"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "merged"
    match_map = tmp_path / "match_map.csv"
    base_dir.mkdir()
    source_dir.mkdir()

    write_rows(
        base_dir / "players.csv",
        player_columns(),
        [
            player_row(
                "2019-005-alex-turcotte",
                "Alex Turcotte",
                source="hockeydb",
                source_id="2019-005-alex-turcotte",
            )
        ],
    )
    write_rows(
        base_dir / "season_stat_lines.csv",
        stat_columns(),
        [stat_row("2019-005-alex-turcotte", "USHL", "hockeydb", points="20")],
    )
    write_rows(
        source_dir / "players.csv",
        player_columns(),
        [
            player_row(
                "2019-ep-209490",
                "Alexander Turcotte",
                source="eliteprospects",
                source_id="209490",
            )
        ],
    )
    write_rows(
        source_dir / "season_stat_lines.csv",
        stat_columns(),
        [stat_row("2019-ep-209490", "USDP", "eliteprospects", points="62")],
    )
    write_rows(
        match_map,
        ["source_player_id", "base_player_id", "note"],
        [
            {
                "source_player_id": "2019-ep-209490",
                "base_player_id": "2019-005-alex-turcotte",
                "note": "EP export uses full first name",
            }
        ],
    )

    summary = merge_normalized_source_tables(
        base_dir,
        source_dir,
        output_dir,
        source_name="eliteprospects",
        match_map_path=match_map,
    )
    merged_stats = read_rows(output_dir / "season_stat_lines.csv")

    assert summary.matched_players == 1
    assert summary.manual_matches == 1
    assert summary.name_matches == 0
    assert summary.unmatched_source_players == 0
    assert merged_stats[0]["player_id"] == "2019-005-alex-turcotte"
    assert merged_stats[0]["league"] == "USDP"


def test_generate_match_map_template_suggests_closest_base_names(tmp_path):
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    unmatched_path = tmp_path / "unmatched_source_players.csv"
    output_path = tmp_path / "match_map_template.csv"

    write_rows(
        base_dir / "players.csv",
        player_columns(),
        [
            player_row(
                "2019-005-alex-turcotte",
                "Alex Turcotte",
                source="hockeydb",
                source_id="2019-005-alex-turcotte",
            ),
            player_row(
                "2019-016-alex-newhook",
                "Alex Newhook",
                source="hockeydb",
                source_id="2019-016-alex-newhook",
            ),
        ],
    )
    write_rows(
        unmatched_path,
        player_columns(),
        [
            player_row(
                "2019-ep-209490",
                "Alexander Turcotte",
                source="eliteprospects",
                source_id="209490",
            )
        ],
    )

    rows = generate_match_map_template(base_dir, unmatched_path, output_path)
    written = read_rows(output_path)

    assert rows == written
    assert written[0]["source_player_id"] == "2019-ep-209490"
    assert written[0]["source_name"] == "Alexander Turcotte"
    assert written[0]["base_player_id"] == ""
    assert written[0]["suggested_base_player_id"] == "2019-005-alex-turcotte"
    assert written[0]["suggested_base_name"] == "Alex Turcotte"
    assert float(written[0]["suggested_score"]) > 0.7


def stat_columns():
    return [
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
    ]


def player_columns():
    return [
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


def player_row(player_id: str, name: str, *, source: str, source_id: str):
    return {
        "player_id": player_id,
        "name": name,
        "birth_date": "",
        "nationality": "",
        "position": "C",
        "handedness": "",
        "height_cm": "",
        "weight_kg": "",
        "age_at_draft": "",
        "source": source,
        "source_id": source_id,
        "source_url": "",
    }


def stat_row(player_id: str, league: str, source: str, *, points: str):
    return {
        "player_id": player_id,
        "season": "2018-19",
        "league": league,
        "team": "Example",
        "games": "10",
        "goals": "1",
        "assists": "2",
        "points": points,
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true",
        "source": source,
        "source_id": player_id,
        "source_url": "",
    }


def write_rows(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
