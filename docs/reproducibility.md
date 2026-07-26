# Reproducibility Modes

The repository has three intentionally different operating modes. Use the one that matches the
work, rather than assuming every command can rebuild all data from a clean clone.

## Offline Demo

This is the supported business-demo workflow. It needs no API key, raw source cache, or network
collection after dependencies are installed.

```bash
python3 -m venv .venv
make install-dev
make demo-2025-reproducible
```

Reviewed snapshots currently available offline:

| Draft year | Command | Context |
| --- | --- | --- |
| 2024 | `make demo-year DRAFT_YEAR=2024` | Retrospective board; evidence labels remain prominent. |
| 2025 | `make demo-year DRAFT_YEAR=2025` | Business-demo board with team-depth context. |
| 2026 | `make demo-year DRAFT_YEAR=2026` | Current-class board; no roster-depth scenario until a defensible 2026 snapshot exists. |

Each tracked `data/demo_snapshots/<year>` bundle contains reviewed normalized player tables and a
checksum manifest. The generated site is written to `outputs/demo_<year>_reproducible`.

`make demo-2025-readiness` is an alias for this supported path. The older
`make demo-2025-local-readiness` command is retained only for a machine that has the ignored local
dataset and roster outputs from an ingestion run.

## Year-Parameterized Demos

Build any reviewed snapshot by its draft year:

```bash
make demo-year DRAFT_YEAR=2025
# Equivalent: python -m draft_room_intelligence.cli build-demo-year 2025
```

The command resolves `data/demo_snapshots/<year>`, verifies its checksums, and writes
`outputs/demo_<year>_reproducible`. A missing snapshot is an intentional, clear failure: it means
the class has not yet been reviewed and packaged for offline use. Create one from a local audited
class with `create-demo-snapshot`; historical classes retain their data-quality labels and do not
inherit the special 2025 showcase-player acceptance checks.

## Offline Development

Tests, the pilot dataset, and small fixtures are tracked and can be used from a clean clone:

```bash
make test
make team-depth-sample
make validate-pilot-2019
```

`make check` runs the test suite and the offline demo build. `make lint` remains a separate
technical-debt target until the existing repository-wide Ruff backlog is resolved.

## Online Refresh And Research

Draft collection and league enrichment are intentionally not deterministic from a clean clone.
They need either:

1. a reviewed local cache under ignored `data/raw/`, or
2. live access to the documented provider endpoints.

The output must be audited before it is promoted to a demo snapshot. Do not treat a successful
network call as reproducibility: providers can change content, rate limits, access rules, or
historical coverage.

For a future shared research release, publish a versioned cache bundle outside Git when permitted
by the source license. It must include a manifest with source URLs, collection date, checksums,
parser version, and the resulting normalized class fingerprints.

## Secrets And Optional Tools

Copy `.env.example` to `.env` only when using OpenAI vision for Elite Prospects PDF extraction.
The example intentionally contains no secret values; `.env` remains ignored. The regular demo,
tests, and local ETL operations do not require an OpenAI key.

PDF vision extraction also requires Poppler's `pdftoppm`. Set `PDFTOPPM_PATH=pdftoppm` when it is
on `PATH`, or provide the executable's local absolute path. This tool is not needed for the
offline demo snapshot.
