import json

import pytest

from draft_room_intelligence.data.nhl_outcomes import (
    build_outcome_label_from_cache,
    load_identity_overrides,
    merge_match_rows,
    next_unreviewed_pick,
    resolve_player_id,
    write_match_audit,
    write_time_bounded_outcome_labels,
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


def test_write_time_bounded_outcome_labels_uses_regular_season_through_horizon(tmp_path):
    cache_dir = tmp_path / "cache" / "2019"
    (cache_dir / "players").mkdir(parents=True)
    write_match_audit(
        cache_dir / "player_matches.csv",
        [
            {
                "draft_year": "2019",
                "overall_pick": "1",
                "player_id": "2019-001-test-player",
                "draft_source_id": "2019-1",
                "name": "Test Player",
                "nhl_player_id": "99",
                "status": "matched",
            }
        ],
    )
    (cache_dir / "players" / "99.json").write_text(
        json.dumps(
            {
                "seasonTotals": [
                    {
                        "leagueAbbrev": "NHL",
                        "gameTypeId": 2,
                        "season": 20192020,
                        "gamesPlayed": 10,
                        "points": 5,
                        "avgToi": "10:00",
                    },
                    {
                        "leagueAbbrev": "NHL",
                        "gameTypeId": 3,
                        "season": 20202021,
                        "gamesPlayed": 4,
                        "points": 2,
                        "avgToi": "10:00",
                    },
                    {
                        "leagueAbbrev": "NHL",
                        "gameTypeId": 2,
                        "season": 20222023,
                        "gamesPlayed": 20,
                        "points": 10,
                        "avgToi": "12:00",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "draft_selections.csv").write_text(
        "draft_year,overall_pick,player_id\n2019,1,canonical-test-player\n",
        encoding="utf-8",
    )
    paths = write_time_bounded_outcome_labels(
        tmp_path / "cache", tmp_path / "labels", draft_year=2019, snapshot_dir=snapshot_dir
    )
    rows = (paths[0]).read_text(encoding="utf-8").splitlines()
    assert "canonical-test-player,2019,3,2022-06-30,10,5,100.0" in rows[1]


def test_write_time_bounded_outcome_labels_rejects_missing_season_totals(tmp_path):
    cache_dir = tmp_path / "cache" / "2019"
    (cache_dir / "players").mkdir(parents=True)
    write_match_audit(
        cache_dir / "player_matches.csv",
        [
            {
                "draft_year": "2019",
                "overall_pick": "1",
                "player_id": "synthetic",
                "draft_source_id": "2019-1",
                "name": "Test",
                "nhl_player_id": "99",
                "status": "matched",
            }
        ],
    )
    (cache_dir / "players" / "99.json").write_text("{}", encoding="utf-8")
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "draft_selections.csv").write_text(
        "draft_year,overall_pick,player_id\n2019,1,canonical\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="seasonTotals"):
        write_time_bounded_outcome_labels(
            tmp_path / "cache", tmp_path / "labels", draft_year=2019, snapshot_dir=snapshot_dir
        )


def test_write_time_bounded_outcome_labels_rejects_stale_audit_year(tmp_path):
    cache_dir = tmp_path / "cache" / "2019"
    cache_dir.mkdir(parents=True)
    write_match_audit(
        cache_dir / "player_matches.csv",
        [
            {
                "draft_year": "2018",
                "overall_pick": "1",
                "player_id": "synthetic",
                "draft_source_id": "2018-1",
                "name": "Test",
                "nhl_player_id": "99",
                "status": "matched",
            }
        ],
    )
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "draft_selections.csv").write_text(
        "draft_year,overall_pick,player_id\n2019,1,canonical\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="invalid match audit row"):
        write_time_bounded_outcome_labels(
            tmp_path / "cache", tmp_path / "labels", draft_year=2019, snapshot_dir=snapshot_dir
        )


def test_write_time_bounded_outcome_labels_rejects_partial_class_and_invalid_season(tmp_path):
    cache_dir = tmp_path / "cache" / "2019"
    (cache_dir / "players").mkdir(parents=True)
    write_match_audit(
        cache_dir / "player_matches.csv",
        [
            {
                "draft_year": "2019",
                "overall_pick": "1",
                "player_id": "synthetic",
                "draft_source_id": "2019-1",
                "name": "Test",
                "nhl_player_id": "99",
                "status": "matched",
            }
        ],
    )
    (cache_dir / "players" / "99.json").write_text(
        json.dumps(
            {
                "seasonTotals": [
                    {
                        "leagueAbbrev": "NHL",
                        "gameTypeId": 2,
                        "season": "",
                        "gamesPlayed": 1,
                        "points": 1,
                        "avgToi": "10:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "draft_selections.csv").write_text(
        "draft_year,overall_pick,player_id\n2019,1,canonical\n2019,2,unmatched\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="partial canonical"):
        write_time_bounded_outcome_labels(
            tmp_path / "cache", tmp_path / "labels", draft_year=2019, snapshot_dir=snapshot_dir
        )
    (snapshot_dir / "draft_selections.csv").write_text(
        "draft_year,overall_pick,player_id\n2019,1,canonical\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="season identifier"):
        write_time_bounded_outcome_labels(
            tmp_path / "cache", tmp_path / "labels", draft_year=2019, snapshot_dir=snapshot_dir
        )


def test_load_identity_overrides_rejects_duplicates_and_requires_provenance(tmp_path):
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        "draft_year,overall_pick,nhl_player_id,reason,source_url\n"
        "2019,1,99,verified,https://api-web.nhle.com/v1/player/99/landing\n"
        "2019,1,100,verified,https://api-web.nhle.com/v1/player/100/landing\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_identity_overrides(overrides, 2019, {1})


def test_build_outcome_label_uses_goalie_time_on_ice_and_zero_points(tmp_path):
    cache_dir = tmp_path / "cache"
    (cache_dir / "players").mkdir(parents=True)
    (cache_dir / "players" / "99.json").write_text(
        json.dumps(
            {
                "seasonTotals": [
                    {
                        "leagueAbbrev": "NHL",
                        "gameTypeId": 2,
                        "season": 20192020,
                        "gamesPlayed": 1,
                        "gamesStarted": 1,
                        "timeOnIce": "59:30",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    row = build_outcome_label_from_cache(
        {"player_id": "synthetic", "nhl_player_id": "99"}, cache_dir, 2019, 3
    )
    assert row["nhl_points"] == "0"
    assert row["nhl_toi_minutes"] == "59.5"
    assert row["goalie_starts"] == "1"
