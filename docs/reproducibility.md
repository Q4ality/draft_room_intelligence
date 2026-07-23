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

The tracked `data/demo_snapshots/2025` bundle contains the reviewed normalized player tables,
advanced statistics, team-depth input, and a checksum manifest. The generated site is written to
`outputs/demo_2025_reproducible`.

`make demo-2025-readiness` is an alias for this supported path. The older
`make demo-2025-local-readiness` command is retained only for a machine that has the ignored local
dataset and roster outputs from an ingestion run.

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
