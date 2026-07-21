import csv
import json

import pytest

from draft_room_intelligence.data.nhl_contracts import (
    enrich_roster_contracts,
    file_sha256,
    normalize_contract_export,
    normalize_trade_protection,
)
from draft_room_intelligence.data.team_rosters import (
    RosterPlayer,
    build_depth_rows,
    load_roster_csv,
    write_roster_csv,
)
from draft_room_intelligence.reports.demo_export import contract_opportunity_score


def test_contract_overlay_matches_source_id_and_builds_commitment(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    contracts_csv = tmp_path / "contracts.csv"
    output_csv = tmp_path / "enriched.csv"
    audit_csv = tmp_path / "audit.csv"
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "nhl-1",
                "Core Defender",
                "D",
                age=26.0,
                games=82,
                snapshot_date="2025-06-01",
                snapshot_type="season_roster",
                source_id="1",
            ),
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "nhl-2",
                "Depth Defender",
                "D",
                age=31.0,
                games=35,
                snapshot_date="2025-06-01",
                snapshot_type="season_roster",
                source_id="2",
            ),
        ],
    )
    with contracts_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "team_id",
                "player_id",
                "player_name",
                "cap_hit",
                "contract_end_year",
                "contract_years_remaining",
                "contract_type",
                "trade_protection",
                "snapshot_date",
                "source",
                "source_url",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "team_id": "NYI",
                "player_id": "1",
                "player_name": "Core Defender",
                "cap_hit": "$8,000,000",
                "contract_end_year": "2030",
                "contract_years_remaining": "5",
                "contract_type": "standard",
                "trade_protection": "NMC",
                "snapshot_date": "2025-06-01",
                "source": "puckpedia",
                "source_url": "https://example.test/core",
            }
        )

    summary = enrich_roster_contracts(roster_csv, contracts_csv, output_csv, audit_csv=audit_csv)
    players = load_roster_csv(output_csv)
    depth = build_depth_rows(players)[0].to_dict()

    assert summary.matched_players == 1
    assert summary.matched_nhl_players == 1
    assert summary.eligible_nhl_players == 2
    assert summary.nhl_coverage == 0.5
    assert players[0].cap_hit == 8_000_000
    assert players[0].trade_protection == "NMC"
    assert players[0].trade_protection_type == "no_move"
    assert players[0].trade_restriction_share == 1.0
    assert players[0].contract_snapshot_date == "2025-06-01"
    assert depth["contract_coverage"] == "0.500"
    assert depth["long_term_committed"] == "1"
    assert float(depth["contract_commitment_score"]) > 0
    assert contract_opportunity_score(depth) < 1.0
    assert depth["roster_flexibility_score"] == "0.000"


def test_trade_protection_normalization_distinguishes_clause_flexibility():
    assert normalize_trade_protection("NMC") == ("no_move", 1.0)
    assert normalize_trade_protection("Full NTC") == ("no_trade", 1.0)
    assert normalize_trade_protection("10-team no-trade list") == ("modified_no_trade", 0.3125)
    assert normalize_trade_protection("15-team trade list") == ("modified_no_trade", 17 / 32)
    assert normalize_trade_protection("") == ("none", 0.0)


def test_missing_contract_coverage_is_neutral():
    assert contract_opportunity_score({"contract_coverage": "0"}) == 0.50
    player = RosterPlayer("NYI", "New York Islanders", "NHL", "", "1", "Unknown Contract", "D")
    depth = build_depth_rows([player])[0].to_dict()
    assert depth["roster_flexibility_score"] == ""


def test_contract_overlay_rejects_wrong_team_or_snapshot(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    contracts_csv = tmp_path / "contracts.csv"
    output_csv = tmp_path / "enriched.csv"
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "nhl-1",
                "Historical Player",
                "D",
                snapshot_date="2025-06-01",
                source_id="1",
            )
        ],
    )
    with contracts_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["team_id", "player_id", "player_name", "cap_hit", "contract_end_year", "snapshot_date"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "team_id": "TOR",
                "player_id": "1",
                "player_name": "Historical Player",
                "cap_hit": "8000000",
                "contract_end_year": "2030",
                "snapshot_date": "2026-07-01",
            }
        )
        writer.writerow(
            {
                "team_id": "NYI",
                "player_id": "1",
                "player_name": "Historical Player",
                "cap_hit": "8000000",
                "contract_end_year": "2030",
                "snapshot_date": "2026-07-01",
            }
        )

    summary = enrich_roster_contracts(roster_csv, contracts_csv, output_csv)

    assert summary.matched_players == 0
    assert summary.unmatched_contracts == 2
    assert load_roster_csv(output_csv)[0].cap_hit == 0


def test_normalize_contract_export_rejects_future_and_conflicting_rows(tmp_path):
    raw_csv = tmp_path / "raw.csv"
    metadata_json = tmp_path / "raw.metadata.json"
    output_csv = tmp_path / "normalized.csv"
    audit_csv = tmp_path / "audit.csv"
    with raw_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["Team", "Player.name", "AAV", "End", "Terms", "Signed"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "Team": "New York Islanders",
                    "Player.name": "Core Defender",
                    "AAV": "$8.0M",
                    "End": "2030",
                    "Terms": "NMC",
                    "Signed": "2024-07-01",
                },
                {
                    "Team": "PIT",
                    "Player.name": "Future Signing",
                    "AAV": "$5,000,000",
                    "End": "2029",
                    "Terms": "M-NTC",
                    "Signed": "2025-06-15",
                },
                {
                    "Team": "TOR",
                    "Player.name": "Conflicted Player",
                    "AAV": "$2,000,000",
                    "End": "2027",
                    "Terms": "",
                    "Signed": "2024-07-01",
                },
                {
                    "Team": "TOR",
                    "Player.name": "Conflicted Player",
                    "AAV": "$3,000,000",
                    "End": "2028",
                    "Terms": "",
                    "Signed": "2024-07-01",
                },
            ]
        )

    metadata_json.write_text(
        json.dumps(
            {
                "source": "licensed-export",
                "source_url": "https://example.test/export",
                "snapshot_date": "2025-06-01",
                "retrieved_at": "2026-07-21",
                "access_basis": "licensed API export",
                "input_sha256": file_sha256(raw_csv),
            }
        ),
        encoding="utf-8",
    )

    summary = normalize_contract_export(
        raw_csv,
        output_csv,
        snapshot_date="2025-06-01",
        metadata_json=metadata_json,
        audit_csv=audit_csv,
    )

    assert summary.input_rows == 4
    assert summary.normalized_rows == 1
    assert summary.rejected_rows == 3
    assert summary.future_signing_rows == 1
    assert summary.conflicting_duplicate_rows == 2
    rows = list(csv.DictReader(output_csv.open(newline="", encoding="utf-8")))
    assert rows == [
        {
            "team_id": "NYI",
            "player_id": "",
            "player_name": "Core Defender",
            "cap_hit": "8000000",
            "contract_end_year": "2030",
            "contract_years_remaining": "5.0",
            "contract_type": "",
            "trade_protection": "NMC",
            "snapshot_date": "2025-06-01",
            "source": "licensed-export",
            "source_url": "https://example.test/export",
        }
    ]
    audit = list(csv.DictReader(audit_csv.open(newline="", encoding="utf-8")))
    assert {row["reason"] for row in audit if row["status"] == "rejected"} == {
        "future_signing",
        "conflicting_duplicate",
    }


def test_contract_match_audit_includes_uncovered_nhl_players(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    contracts_csv = tmp_path / "contracts.csv"
    output_csv = tmp_path / "enriched.csv"
    audit_csv = tmp_path / "audit.csv"
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "1",
                "Covered Player",
                "D",
                snapshot_date="2025-06-01",
                source_id="1",
            ),
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "2",
                "Missing Player",
                "D",
                snapshot_date="2025-06-01",
                source_id="2",
            ),
        ],
    )
    with contracts_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "team_id",
                "player_id",
                "player_name",
                "cap_hit",
                "contract_end_year",
                "snapshot_date",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "team_id": "NYI",
                "player_id": "1",
                "player_name": "Covered Player",
                "cap_hit": "1000000",
                "contract_end_year": "2026",
                "snapshot_date": "2025-06-01",
            }
        )

    summary = enrich_roster_contracts(roster_csv, contracts_csv, output_csv, audit_csv=audit_csv)
    audit = list(csv.DictReader(audit_csv.open(newline="", encoding="utf-8")))

    assert summary.nhl_coverage == 0.5
    assert any(
        row["status"] == "missing_contract" and row["player_name"] == "Missing Player"
        for row in audit
    )


def test_overlay_clears_unverified_existing_contract_data(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    contracts_csv = tmp_path / "contracts.csv"
    output_csv = tmp_path / "enriched.csv"
    audit_csv = tmp_path / "audit.csv"
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "1",
                "Future Data Player",
                "D",
                snapshot_date="2025-06-01",
                cap_hit=9_000_000,
                contract_end_year=2032,
                contract_snapshot_date="2026-07-01",
                contract_source="future-source",
            )
        ],
    )
    with contracts_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "team_id",
                "player_name",
                "cap_hit",
                "contract_end_year",
                "snapshot_date",
            ],
        )
        writer.writeheader()

    summary = enrich_roster_contracts(roster_csv, contracts_csv, output_csv, audit_csv=audit_csv)
    player = load_roster_csv(output_csv)[0]
    depth = build_depth_rows([player])[0].to_dict()
    audit = list(csv.DictReader(audit_csv.open(newline="", encoding="utf-8")))

    assert summary.nhl_coverage == 0.0
    assert player.cap_hit == 0
    assert player.contract_snapshot_date == ""
    assert depth["contract_coverage"] == "0.000"
    assert any(row["status"] == "cleared_existing_contract" for row in audit)


def test_overlay_fails_closed_for_wrong_id_and_duplicate_target(tmp_path):
    roster_csv = tmp_path / "roster.csv"
    contracts_csv = tmp_path / "contracts.csv"
    output_csv = tmp_path / "enriched.csv"
    audit_csv = tmp_path / "audit.csv"
    write_roster_csv(
        roster_csv,
        [
            RosterPlayer(
                "NYI",
                "New York Islanders",
                "NHL",
                "",
                "1",
                "Known Player",
                "D",
                snapshot_date="2025-06-01",
                source_id="1",
            )
        ],
    )
    with contracts_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=NORMALIZED_TEST_COLUMNS)
        writer.writeheader()
        writer.writerows(
            [
                normalized_contract_row(player_id="999", cap_hit="9000000"),
                normalized_contract_row(player_id="1", cap_hit="1000000"),
                normalized_contract_row(player_id="1", cap_hit="2000000"),
            ]
        )

    summary = enrich_roster_contracts(roster_csv, contracts_csv, output_csv, audit_csv=audit_csv)
    audit = list(csv.DictReader(audit_csv.open(newline="", encoding="utf-8")))

    assert summary.matched_players == 1
    assert summary.unmatched_contracts == 1
    assert summary.ambiguous_contracts == 1
    assert load_roster_csv(output_csv)[0].cap_hit == 1_000_000
    assert any(row["status"] == "unmatched" and row["player_id"] == "999" for row in audit)
    assert any(row["status"] == "duplicate_target" for row in audit)


def test_normalizer_requires_matching_metadata_and_audits_bad_values(tmp_path):
    raw_csv = tmp_path / "raw.csv"
    metadata_json = tmp_path / "raw.metadata.json"
    output_csv = tmp_path / "normalized.csv"
    audit_csv = tmp_path / "audit.csv"
    with raw_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["Team", "Player", "AAV", "End", "Signed"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"Team": "NYI", "Player": "Tiny Cap", "AAV": "8.0", "End": "2030", "Signed": ""},
                {
                    "Team": "NYI",
                    "Player": "Bad Date",
                    "AAV": "$1,000,000",
                    "End": "2030",
                    "Signed": "not-a-date",
                },
            ]
        )
    metadata = {
        "source": "licensed-export",
        "source_url": "https://example.test/export",
        "snapshot_date": "2025-06-01",
        "retrieved_at": "2026-07-21",
        "access_basis": "licensed API export",
        "input_sha256": file_sha256(raw_csv),
    }
    metadata_json.write_text(json.dumps(metadata), encoding="utf-8")

    summary = normalize_contract_export(
        raw_csv,
        output_csv,
        snapshot_date="2025-06-01",
        metadata_json=metadata_json,
        audit_csv=audit_csv,
    )
    audit = list(csv.DictReader(audit_csv.open(newline="", encoding="utf-8")))

    assert summary.normalized_rows == 0
    assert {row["reason"] for row in audit} == {"implausible_cap_hit", "malformed_value"}

    metadata["input_sha256"] = "0" * 64
    metadata_json.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        normalize_contract_export(
            raw_csv,
            output_csv,
            snapshot_date="2025-06-01",
            metadata_json=metadata_json,
        )

    metadata["input_sha256"] = file_sha256(raw_csv)
    metadata["source"] = ""
    metadata_json.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="identify the source"):
        normalize_contract_export(
            raw_csv,
            output_csv,
            snapshot_date="2025-06-01",
            metadata_json=metadata_json,
        )


NORMALIZED_TEST_COLUMNS = [
    "team_id",
    "player_id",
    "player_name",
    "cap_hit",
    "contract_end_year",
    "snapshot_date",
]


def normalized_contract_row(*, player_id: str, cap_hit: str) -> dict[str, str]:
    return {
        "team_id": "NYI",
        "player_id": player_id,
        "player_name": "Known Player",
        "cap_hit": cap_hit,
        "contract_end_year": "2030",
        "snapshot_date": "2025-06-01",
    }
