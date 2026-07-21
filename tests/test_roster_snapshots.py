import csv
import hashlib
import json

import pytest

from draft_room_intelligence.data.roster_snapshots import (
    NHL_TEAM_IDS,
    build_point_in_time_roster,
    normalize_roster_snapshot,
)
from draft_room_intelligence.data.team_rosters import (
    RosterPlayer,
    load_roster_csv,
    write_roster_csv,
)


def write_source(
    tmp_path, rows, *, scope="full_league_rights_snapshot", snapshot_date="2025-06-01"
):
    source = tmp_path / "raw.csv"
    columns = [
        "team",
        "nhl_id",
        "player",
        "pos",
        "level",
        "status",
        "age",
        "effective_date",
    ]
    with source.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = tmp_path / "raw.metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "source": "licensed-rights-export",
                "source_url": "https://example.test/export",
                "snapshot_date": snapshot_date,
                "retrieved_at": "2026-07-21",
                "access_basis": "licensed export",
                "scope": scope,
                "input_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    return source, metadata


def test_normalize_roster_snapshot_rejects_future_assignment_and_writes_audit(tmp_path):
    source, metadata = write_source(
        tmp_path,
        [
            {
                "team": "New York Islanders",
                "nhl_id": "1",
                "player": "Existing Defender",
                "pos": "D",
                "level": "NHL",
                "status": "Active roster",
                "age": "22",
                "effective_date": "2024-10-01",
            },
            {
                "team": "PIT",
                "nhl_id": "2",
                "player": "Future Signing",
                "pos": "G",
                "level": "AHL",
                "status": "Under contract",
                "age": "21",
                "effective_date": "2025-07-01",
            },
        ],
    )
    output = tmp_path / "normalized.csv"
    audit = tmp_path / "audit.csv"

    summary = normalize_roster_snapshot(
        source,
        output,
        snapshot_date="2025-06-01",
        metadata_json=metadata,
        audit_csv=audit,
        minimum_team_count=1,
        minimum_player_count=1,
        minimum_players_per_team=1,
    )

    assert summary.normalized_rows == 1
    assert summary.rejected_rows == 1
    rows = list(csv.DictReader(output.open(newline="", encoding="utf-8")))
    assert rows[0]["team_id"] == "NYI"
    assert rows[0]["snapshot_date"] == "2025-06-01"
    assert "future_assignment" in audit.read_text(encoding="utf-8")


def test_normalize_roster_snapshot_fails_closed_on_partial_scope(tmp_path):
    source, metadata = write_source(tmp_path, [], scope="sample")

    with pytest.raises(ValueError, match="scope must be full_league_rights_snapshot"):
        normalize_roster_snapshot(
            source,
            tmp_path / "normalized.csv",
            snapshot_date="2025-06-01",
            metadata_json=metadata,
            minimum_team_count=0,
            minimum_player_count=0,
            minimum_players_per_team=0,
        )


def test_normalize_roster_snapshot_requires_league_wide_team_coverage(tmp_path):
    source, metadata = write_source(
        tmp_path,
        [
            {
                "team": "NYI",
                "player": "Only Player",
                "pos": "D",
                "level": "NHL",
                "status": "active",
            }
        ],
    )

    with pytest.raises(ValueError, match="covers 1 teams; at least 32"):
        normalize_roster_snapshot(
            source,
            tmp_path / "normalized.csv",
            snapshot_date="2025-06-01",
            metadata_json=metadata,
        )


def test_normalize_roster_snapshot_rejects_implausibly_thin_full_league_export(tmp_path):
    rows = [
        {
            "team": team_id,
            "nhl_id": str(index),
            "player": f"Player {index}",
            "pos": "D",
            "level": "PROSPECT",
            "status": "reserve list",
        }
        for index, team_id in enumerate(sorted(NHL_TEAM_IDS), start=1)
    ]
    source, metadata = write_source(tmp_path, rows)

    with pytest.raises(ValueError, match="at least 480"):
        normalize_roster_snapshot(
            source,
            tmp_path / "normalized.csv",
            snapshot_date="2025-06-01",
            metadata_json=metadata,
        )


def test_normalize_roster_snapshot_rejects_unknown_position(tmp_path):
    source, metadata = write_source(
        tmp_path,
        [
            {
                "team": "NYI",
                "player": "Unknown Role",
                "pos": "UTILITY",
                "level": "NHL",
                "status": "active",
            }
        ],
    )
    audit = tmp_path / "audit.csv"

    summary = normalize_roster_snapshot(
        source,
        tmp_path / "normalized.csv",
        snapshot_date="2025-06-01",
        metadata_json=metadata,
        audit_csv=audit,
        minimum_team_count=0,
        minimum_player_count=0,
        minimum_players_per_team=0,
    )

    assert summary.normalized_rows == 0
    assert "invalid_position" in audit.read_text(encoding="utf-8")


def test_build_point_in_time_roster_reassigns_adds_and_excludes(tmp_path):
    base = tmp_path / "base.csv"
    write_roster_csv(
        base,
        [
            RosterPlayer(
                "TOR",
                "Toronto Maple Leafs",
                "AHL",
                "Toronto Marlies",
                "ahl-1",
                "Moved Prospect",
                "D",
                age=21.5,
                games=45,
                source_id="100",
            ),
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "nhl-2",
                "Stale Player",
                "C",
                source_id="200",
            ),
        ],
    )
    snapshot = tmp_path / "snapshot.csv"
    rows = [
        {
            "team_id": "PIT", "player_id": "100", "player_name": "Moved Prospect", "position": "D",
            "league_level": "AHL", "roster_status": "under_contract", "age": "21.5",
            "effective_date": "2025-03-01", "snapshot_date": "2025-06-01", "source": "rights",
            "source_url": "https://example.test/rights",
        },
        {
            "team_id": "NYI", "player_id": "300", "player_name": "Reserve Prospect",
            "position": "G",
            "league_level": "PROSPECT", "roster_status": "reserve_list", "age": "19.0",
            "effective_date": "2024-06-29", "snapshot_date": "2025-06-01", "source": "rights",
            "source_url": "https://example.test/rights",
        },
    ]
    with snapshot.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    output = tmp_path / "point_in_time.csv"
    audit = tmp_path / "build_audit.csv"
    summary = build_point_in_time_roster(
        base,
        snapshot,
        output,
        expected_snapshot_date="2025-06-01",
        audit_csv=audit,
        minimum_team_count=0,
        minimum_player_count=0,
        minimum_players_per_team=0,
    )
    players = {player.player_name: player for player in load_roster_csv(output)}

    assert summary.matched_players == 1
    assert summary.sparse_players == 1
    assert summary.excluded_base_players == 1
    assert players["Moved Prospect"].team_id == "PIT"
    assert players["Moved Prospect"].games == 45
    assert players["Moved Prospect"].snapshot_type == "point_in_time_rights"
    assert players["Moved Prospect"].assignment_source == "rights"
    assert players["Reserve Prospect"].league_level == "PROSPECT"
    assert players["Reserve Prospect"].source == "rights"
    assert "excluded_not_in_rights_snapshot" in audit.read_text(encoding="utf-8")


def test_build_point_in_time_roster_rejects_duplicate_assignments(tmp_path):
    base = tmp_path / "base.csv"
    write_roster_csv(base, [])
    snapshot = tmp_path / "snapshot.csv"
    row = {
        "team_id": "NYI", "player_id": "1", "player_name": "Duplicate", "position": "D",
        "league_level": "NHL", "roster_status": "active", "age": "", "effective_date": "",
        "snapshot_date": "2025-06-01", "source": "rights", "source_url": "https://example.test",
    }
    with snapshot.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerows([row, {**row, "team_id": "PIT"}])

    with pytest.raises(ValueError, match="duplicate player assignments"):
        build_point_in_time_roster(
            base,
            snapshot,
            tmp_path / "output.csv",
            expected_snapshot_date="2025-06-01",
        )


def test_build_point_in_time_roster_rechecks_full_league_coverage(tmp_path):
    base = tmp_path / "base.csv"
    write_roster_csv(base, [])
    snapshot = tmp_path / "snapshot.csv"
    row = {
        "team_id": "NYI", "player_id": "1", "player_name": "Only Player", "position": "D",
        "league_level": "NHL", "roster_status": "active", "age": "20.0", "effective_date": "",
        "snapshot_date": "2025-06-01", "source": "rights", "source_url": "https://example.test",
    }
    with snapshot.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    with pytest.raises(ValueError, match="covers 1 teams; at least 32"):
        build_point_in_time_roster(
            base,
            snapshot,
            tmp_path / "output.csv",
            expected_snapshot_date="2025-06-01",
        )


def test_normalize_roster_snapshot_rejects_every_conflicting_assignment(tmp_path):
    common = {
        "nhl_id": "1",
        "player": "Conflicted Player",
        "pos": "C/LW",
        "level": "NHL",
        "status": "active",
        "effective_date": "2025-01-01",
    }
    source, metadata = write_source(
        tmp_path,
        [{**common, "team": "NYI"}, {**common, "team": "PIT", "nhl_id": ""}],
    )
    output = tmp_path / "normalized.csv"
    audit = tmp_path / "audit.csv"

    summary = normalize_roster_snapshot(
        source,
        output,
        snapshot_date="2025-06-01",
        metadata_json=metadata,
        audit_csv=audit,
        minimum_team_count=0,
        minimum_player_count=0,
        minimum_players_per_team=0,
    )

    assert summary.normalized_rows == 0
    assert audit.read_text(encoding="utf-8").count("conflicting_assignment") == 2


def test_normalize_roster_snapshot_keeps_namesakes_with_distinct_ids(tmp_path):
    common = {
        "player": "Alex Smith",
        "pos": "D",
        "level": "PROSPECT",
        "status": "reserve_list",
    }
    source, metadata = write_source(
        tmp_path,
        [
            {**common, "team": "NYI", "nhl_id": "1"},
            {**common, "team": "PIT", "nhl_id": "2"},
            {**common, "team": "TOR", "nhl_id": "3", "player": "Иван Иванов"},
        ],
    )

    summary = normalize_roster_snapshot(
        source,
        tmp_path / "normalized.csv",
        snapshot_date="2025-06-01",
        metadata_json=metadata,
        minimum_team_count=0,
        minimum_player_count=0,
        minimum_players_per_team=0,
    )

    assert summary.normalized_rows == 3


def test_build_point_in_time_roster_does_not_match_wrong_id_name_pair(tmp_path):
    base = tmp_path / "base.csv"
    write_roster_csv(
        base,
        [
            RosterPlayer(
                "NYI", "New York Islanders", "NHL", "", "nhl-1", "Actual Player", "D",
                games=82, source_id="1",
            )
        ],
    )
    snapshot = tmp_path / "snapshot.csv"
    row = {
        "team_id": "NYI", "player_id": "1", "player_name": "Different Player", "position": "D",
        "league_level": "NHL", "roster_status": "active", "age": "20.0", "effective_date": "",
        "snapshot_date": "2025-06-01", "source": "rights", "source_url": "https://example.test",
    }
    with snapshot.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    output = tmp_path / "output.csv"
    summary = build_point_in_time_roster(
        base,
        snapshot,
        output,
        expected_snapshot_date="2025-06-01",
        minimum_team_count=0,
        minimum_player_count=0,
        minimum_players_per_team=0,
    )

    assert summary.matched_players == 0
    player = load_roster_csv(output)[0]
    assert player.player_name == "Different Player"
    assert player.games == 0
