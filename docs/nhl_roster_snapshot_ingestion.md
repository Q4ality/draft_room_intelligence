# Historical NHL Roster Snapshot Ingestion

## Purpose

The current 2025 team-fit input is a 2024-25 season-participation proxy. It is useful for prior-season performance, but it is not proof of organizational rights at a specific date. The point-in-time pipeline keeps those concepts separate:

1. A permitted full-league rights inventory establishes organization, roster level, and status at the cutoff.
2. Cached NHL/AHL season rows contribute prior-season statistics where identity matching is unambiguous.
3. Rights holders without prior-season NHL/AHL rows remain visible as sparse prospect rows.
4. Season participants absent from the rights inventory are excluded and recorded in the audit.

The intended 2025 cutoff is `2025-06-01`, before the 2025 draft and aligned with the contract snapshot design. It should be described as a pre-draft snapshot, not a draft-night snapshot.

## Required Source

The source must be a permitted export or API result covering all 32 NHL organizations. Each row needs:

- organization/team;
- player name and preferably a stable NHL player ID;
- position;
- roster level: `NHL`, `AHL`, or `PROSPECT`;
- rights/roster status;
- optional age and assignment/acquisition effective date.

Store the raw export under `data/raw/rosters/rights/2025-06-01/`. Add a JSON metadata sidecar:

```json
{
  "source": "source name",
  "source_url": "https://source.example/export",
  "snapshot_date": "2025-06-01",
  "retrieved_at": "2026-07-21",
  "access_basis": "licensed export or documented API permission",
  "scope": "full_league_rights_snapshot",
  "input_sha256": "sha256 of the raw CSV"
}
```

The normalizer fails closed on a wrong checksum, partial scope, fewer than 32 teams, fewer than 480 players, fewer than 10 players for any organization, conflicting player assignments, invalid teams/positions, or an effective date after the cutoff. These are plausibility floors, not evidence that the source is complete; source licensing and scope still need review.

## Runbook

```bash
PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli normalize-roster-snapshot \
  data/raw/rosters/rights/2025-06-01/rights_raw.csv \
  data/raw/rosters/rights/2025-06-01/rights_normalized.csv \
  --snapshot-date 2025-06-01 \
  --metadata-json data/raw/rosters/rights/2025-06-01/rights_raw.metadata.json \
  --audit-csv outputs/roster_snapshot_normalization_audit.csv

PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli build-point-in-time-roster \
  outputs/org_rosters_2024_25_with_ahl.csv \
  data/raw/rosters/rights/2025-06-01/rights_normalized.csv \
  outputs/org_rosters_2025_06_01_rights.csv \
  --snapshot-date 2025-06-01 \
  --audit-csv outputs/roster_snapshot_build_audit.csv

PYTHONPATH=src .venv/bin/python -m draft_room_intelligence.cli report-team-depth \
  outputs/org_rosters_2025_06_01_rights.csv \
  outputs/org_team_depth_2025_06_01_rights
```

Use the resulting depth CSV in `build-demo-readiness`. The demo reads `snapshot_types` from the data and only displays the verified point-in-time label when every row reports `point_in_time_rights`.

## Current Gate

No permitted full-league rights inventory is staged in the repository. Therefore the current demo must continue using and labeling the season-participation proxy. The adapter is ready; source acquisition and licensing remain the external gate.
