import csv

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    write_table,
)
from draft_room_intelligence.data.open_stats_csv import OpenStatsCsvSource, enrich_open_stats_csv


def test_enrich_open_stats_csv_replaces_placeholder_and_keeps_goalie_metrics(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "ncaa.csv"
    base_dir.mkdir()
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "name": "James Hagens",
                "birth_date": "",
                "nationality": "United States",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-007-james-hagens",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "season": "2024-25",
                "league": "NCAA",
                "team": "Boston College",
                "games": "",
                "goals": "",
                "assists": "",
                "points": "",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia",
                "source_id": "2025-007-james-hagens",
                "source_url": "",
            }
        ],
    )
    source_path.write_text(
        "\n".join(
            [
                "name,league,team,games,goals,assists,points,source_url",
                "James Hagens,NCAA,Boston College,37,11,26,37,https://example.test/james-hagens",
            ]
        ),
        encoding="utf-8",
    )

    summary = enrich_open_stats_csv(
        base_dir,
        output_dir,
        [
            OpenStatsCsvSource(
                path=source_path, source="collegehockeyinc", season="2024-25", league="NCAA"
            )
        ],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 1
    assert stat_lines[0]["source"] == "open-stats"
    assert stat_lines[0]["games"] == "37"
    assert stat_lines[0]["points"] == "37"
    assert stat_lines[0]["source_url"] == "https://example.test/james-hagens"


def test_enrich_open_stats_csv_can_append_curated_new_league_rows(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "ushl.csv"
    base_dir.mkdir()
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "name": "James Hagens",
                "birth_date": "",
                "nationality": "United States",
                "position": "C",
                "handedness": "",
                "height_cm": "",
                "weight_kg": "",
                "age_at_draft": "",
                "source": "wikipedia",
                "source_id": "2025-007-james-hagens",
                "source_url": "",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-007-james-hagens",
                "season": "2024-25",
                "league": "NCAA",
                "team": "Boston College",
                "games": "37",
                "goals": "11",
                "assists": "26",
                "points": "37",
                "age": "",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "wikipedia-career",
                "source_id": "James Hagens",
                "source_url": "",
            }
        ],
    )
    source_path.write_text(
        "\n".join(
            [
                "name,season,league,team,games,goals,assists,points,source_url",
                "James Hagens,2023-24,USHL,U.S. National Development Team,26,18,29,47,https://example.test/james-hagens",
            ]
        ),
        encoding="utf-8",
    )

    summary = enrich_open_stats_csv(
        base_dir,
        output_dir,
        [OpenStatsCsvSource(path=source_path, source="curated", season="2023-24")],
        allow_new_leagues=True,
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.matched_players == 1
    assert len(stat_lines) == 2
    assert {row["league"] for row in stat_lines} == {"NCAA", "USHL"}


def test_enrich_open_stats_csv_reconciles_russian_team_aliases(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "out"
    source_path = tmp_path / "mhl.csv"
    base_dir.mkdir()
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [
            {
                "player_id": "2025-199-pyotr-andreyanov",
                "name": "Pyotr Andreyanov",
                "position": "G",
            }
        ],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "2025-199-pyotr-andreyanov",
                "season": "2024-25",
                "league": "MHL",
                "team": "Krasnaya Armiya Moskva",
                "games": "37",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "eliteprospects_pdf",
                "source_id": "2025-ep-pdf-page-99",
            }
        ],
    )
    source_path.write_text(
        "\n".join(
            [
                "name,season,league,team,games,save_percentage,goals_against_average,regular_season,source_url",
                "Pyotr Andreyanov,2024-25,MHL,Krasnaya Armiya,37,.942,1.75,true,https://example.test/andreyanov",
                "Pyotr Andreyanov,2024-25,MHL,Krasnaya Armiya,6,.929,2.36,false,https://example.test/andreyanov",
            ]
        ),
        encoding="utf-8",
    )

    summary = enrich_open_stats_csv(
        base_dir,
        output_dir,
        [OpenStatsCsvSource(path=source_path, source="reviewed", season="2024-25")],
    )

    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))

    assert summary.output_stat_lines == 2
    regular = next(row for row in stat_lines if row["regular_season"] == "true")
    playoffs = next(row for row in stat_lines if row["regular_season"] == "false")
    assert regular["games"] == "37"
    assert regular["save_percentage"] == "0.942"
    assert set(regular["source"].split("; ")) == {"eliteprospects_pdf", "open-stats"}
    assert playoffs["games"] == "6"

    with (output_dir / "stat_line_reconciliation_audit.csv").open(
        newline="", encoding="utf-8"
    ) as file:
        audit_rows = list(csv.DictReader(file))
    assert len(audit_rows) == 1
    assert audit_rows[0]["row_count"] == "2"


def test_enrich_open_stats_csv_fills_blank_nationality_from_reviewed_row(tmp_path):
    base_dir = tmp_path / "base"
    output_dir = tmp_path / "output"
    base_dir.mkdir()
    write_table(
        base_dir / "players.csv",
        PLAYER_COLUMNS,
        [{"player_id": "player-1", "name": "Test Player", "nationality": ""}],
    )
    write_table(
        base_dir / "season_stat_lines.csv",
        SEASON_STAT_LINE_COLUMNS,
        [
            {
                "player_id": "player-1",
                "season": "2018-19",
                "league": "Rus-MHL",
                "team": "Test Club Jr.",
                "games": "40",
                "points": "1200",
                "timing": "pre_draft",
                "regular_season": "true",
                "source": "hockeydb",
            }
        ],
    )
    source_path = tmp_path / "reviewed.csv"
    source_path.write_text(
        "name,nationality,season,league,team,games,goals,assists,points\n"
        "Test Player,RUS,2018-19,MHL,Test Club,40,10,15,25\n",
        encoding="utf-8",
    )

    enrich_open_stats_csv(
        base_dir,
        output_dir,
        [OpenStatsCsvSource(path=source_path, source="reviewed", season="2018-19")],
        allow_new_leagues=True,
    )

    with (output_dir / "players.csv").open(newline="", encoding="utf-8") as file:
        players = list(csv.DictReader(file))
    with (output_dir / "season_stat_lines.csv").open(newline="", encoding="utf-8") as file:
        stat_lines = list(csv.DictReader(file))
    assert players[0]["nationality"] == "RUS"
    assert len(stat_lines) == 1
    assert stat_lines[0]["league"] == "MHL"
    assert stat_lines[0]["points"] == "25"
