from draft_room_intelligence.data.stat_reconciliation import reconcile_stat_lines


def test_reconcile_stat_lines_merges_duplicates_and_reports_conflicts():
    rows = [
        {
            "player_id": "p1",
            "season": "2024-25",
            "league": "OHL",
            "team": "Erie Otters",
            "games": "10",
            "goals": "4",
            "assists": "5",
            "points": "9",
            "age": "",
            "timing": "pre_draft",
            "regular_season": "true",
            "source": "wikipedia",
            "source_id": "wiki",
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
        },
        {
            "player_id": "p1",
            "season": "2024-25",
            "league": "OHL",
            "team": "Erie Otters",
            "games": "10",
            "goals": "5",
            "assists": "5",
            "points": "10",
            "age": "",
            "timing": "pre_draft",
            "regular_season": "true",
            "source": "chl",
            "source_id": "league",
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
        },
    ]

    result = reconcile_stat_lines(rows)

    assert len(result.rows) == 1
    assert result.rows[0]["source"] == "chl; wikipedia"
    assert result.rows[0]["goals"] == "5"
    assert result.rows[0]["points"] == "10"
    assert result.duplicate_groups == 1
    assert result.conflict_groups == 1
    assert result.audit_rows[0]["action"] == "merged_with_conflicts"
    assert "goals" in result.audit_rows[0]["conflict_fields"]


def test_reconcile_stat_lines_matches_chl_team_abbreviation_aliases():
    rows = [
        {
            "player_id": "p1",
            "season": "2024-25",
            "league": "OHL",
            "team": "ER",
            "games": "17",
            "goals": "7",
            "assists": "15",
            "points": "22",
            "age": "",
            "timing": "pre_draft",
            "regular_season": "true",
            "source": "chl",
            "source_id": "8998",
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
        },
        {
            "player_id": "p1",
            "season": "2024-25",
            "league": "OHL",
            "team": "Erie Otters",
            "games": "17",
            "goals": "7",
            "assists": "15",
            "points": "22",
            "age": "",
            "timing": "pre_draft",
            "regular_season": "true",
            "source": "eliteprospects_pdf; wikipedia-career",
            "source_id": "2025-ep-pdf-page-29",
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
        },
    ]

    result = reconcile_stat_lines(rows)

    assert len(result.rows) == 1
    assert result.rows[0]["team"] == "ER"
    merged_sources = set(result.rows[0]["source"].split("; "))
    assert merged_sources == {"chl", "eliteprospects_pdf", "wikipedia-career"}
    assert result.duplicate_groups == 1
    assert result.conflict_groups == 0


def test_reconcile_stat_lines_matches_mhl_translated_team_aliases():
    rows = [
        {
            "player_id": "p1",
            "season": "2024-25",
            "league": "MHL",
            "team": team,
            "games": "37",
            "timing": "pre_draft",
            "regular_season": "true",
            "source": source,
        }
        for team, source in [
            ("Krasnaya Armiya", "open-stats"),
            ("Krasnaya Armiya Moskva", "eliteprospects_pdf"),
        ]
    ]

    result = reconcile_stat_lines(rows)

    assert len(result.rows) == 1
    assert result.duplicate_groups == 1
    assert result.conflict_groups == 0
