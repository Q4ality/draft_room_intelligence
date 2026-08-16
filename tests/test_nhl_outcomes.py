from draft_room_intelligence.data.nhl_outcomes import (
    merge_match_rows,
    next_unreviewed_pick,
    resolve_player_id,
    write_match_audit,
)


def test_resolve_player_id_requires_unique_matching_draft_details():
    landings = {
        1: {"draftDetails": {"year": 2019, "overallPick": 1}},
        2: {"draftDetails": {"year": 1987, "overallPick": 1}},
    }
    assert resolve_player_id(2019, 1, landings) == 1
    assert resolve_player_id(2019, 2, landings) is None


def test_resolve_player_id_rejects_ambiguous_matches():
    landings = {
        1: {"draftDetails": {"year": 2019, "overallPick": 1}},
        2: {"draftDetails": {"year": 2019, "overallPick": 1}},
    }
    assert resolve_player_id(2019, 1, landings) is None


def test_merge_match_rows_replaces_completed_pick_without_losing_prior_batch():
    existing = [{"overall_pick": "1", "status": "unresolved"}]
    new = [
        {"overall_pick": "1", "status": "matched"},
        {"overall_pick": "2", "status": "matched"},
    ]
    assert merge_match_rows(existing, new) == [
        {"overall_pick": "1", "status": "matched"},
        {"overall_pick": "2", "status": "matched"},
    ]


def test_next_unreviewed_pick_advances_from_persisted_audit(tmp_path):
    write_match_audit(
        tmp_path / "player_matches.csv",
        [
            {
                "draft_year": "2019",
                "overall_pick": "1",
                "name": "One",
                "nhl_player_id": "1",
                "status": "matched",
            },
            {
                "draft_year": "2019",
                "overall_pick": "2",
                "name": "Two",
                "nhl_player_id": "",
                "status": "unresolved",
            },
        ],
    )
    assert next_unreviewed_pick(tmp_path) == 3
