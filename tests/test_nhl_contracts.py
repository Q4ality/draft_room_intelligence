import csv

from draft_room_intelligence.data.nhl_contracts import enrich_roster_contracts, normalize_trade_protection
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
    assert players[0].cap_hit == 8_000_000
    assert players[0].trade_protection == "NMC"
    assert players[0].trade_protection_type == "no_move"
    assert players[0].trade_restriction_share == 1.0
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
