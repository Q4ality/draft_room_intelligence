# NHL Contract And Cap Ingestion

## Purpose

Add organizational commitment and mobility evidence to the historical 2025 team-fit snapshot without leaking later transactions into the draft-night view.

The pipeline is cache-first:

1. Obtain a permitted export or API response dated `2025-06-01`.
2. Store the raw file under ignored `data/raw/contracts/2025-06-01/`.
3. Add a metadata sidecar proving the source snapshot, access basis, and raw-file checksum.
4. Normalize source columns and audit rejected rows.
5. Overlay contracts onto the historical roster and audit NHL coverage.
6. Rebuild team depth and the demo only after coverage and snapshot checks pass.

## Required Evidence

Each normalized row must contain:

- team abbreviation or recognized full team name,
- player name and optional NHL/source player ID,
- cap hit or AAV,
- contract end year,
- source snapshot date,
- source label and URL,
- optional contract type and trade-protection clause.

The normalizer accepts common aliases such as `Team`, `Player.name`, `AAV`, `End`, `Terms`, and `Signed`. It rejects invalid teams, missing cap hits or end years, expired contracts, post-snapshot signings, and conflicting duplicate rows.

Create `source-export.metadata.json` beside `source-export.csv`:

```json
{
  "source": "licensed-source-name",
  "source_url": "https://provider.example/export",
  "snapshot_date": "2025-06-01",
  "retrieved_at": "2026-07-21",
  "access_basis": "licensed API export",
  "input_sha256": "<sha256 of source-export.csv>"
}
```

The normalizer verifies the sidecar snapshot and checksum. The ingestion-plan audit treats an empty cache directory or a CSV without its matching `.metadata.json` sidecar as missing.

## Commands

```bash
PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli normalize-nhl-contracts \
  data/raw/contracts/2025-06-01/source-export.csv \
  data/raw/contracts/2025-06-01/contracts.normalized.csv \
  --snapshot-date 2025-06-01 \
  --metadata-json data/raw/contracts/2025-06-01/source-export.metadata.json \
  --audit-csv outputs/contracts_2025_normalization_audit.csv

PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli enrich-roster-contracts \
  outputs/org_rosters_2024_25_with_ahl.csv \
  data/raw/contracts/2025-06-01/contracts.normalized.csv \
  outputs/org_rosters_2024_25_with_ahl_contracts.csv \
  --audit-csv outputs/contracts_2025_match_audit.csv
```

Then rebuild depth using the enriched roster CSV and run `make demo-2025-readiness` after pointing the team-depth build at that output.

## Activation Gate

Contract scoring remains neutral unless the selected role row has at least 50% contract coverage. Before treating the dataset as business-ready, require:

- at least 80% coverage of historical NHL roster players,
- zero future-signing rows in normalized output,
- reviewed ambiguous and unmatched identities,
- exact `2025-06-01` contract and roster snapshot alignment,
- source terms permitting the cached export and analytical use.

## Source Status

- PuckPedia advertises private contract and team-cap APIs; access requires provider approval or credentials.
- The Stanley Cap exposes useful historical tables but its terms prohibit automated scraping, so it is not an ETL source for this project.
- An ODbL Kaggle file pairing 2024-25 statistics with contract fields was evaluated and rejected: its contract values include post-draft updates, so it is not a valid draft-night snapshot.

Until a permitted dated export is staged, `nhl_contracts` remains blocked in the ingestion-plan audit and the demo continues to label contract/cap coverage as not loaded.
