---
name: prepare-draft-demo-data
description: Use this skill when preparing a single draft-year demo dataset for draft-room-intelligence, especially when you need to scaffold expected paths, audit missing raw inputs, stage HockeyDB HTML or Elite Prospects CSV files into the repo, run draft-year ETL, or build the demo site and readiness reports for a showcase class such as 2025.
---

# Prepare Draft Demo Data

Use this skill to prepare a demo-ready draft class inside this repository. It turns a loose collection problem into a repeatable workflow: scaffold the year, audit what is missing, stage files into the right paths, run ETL, and build the demo output with data-gap and modeling sanity reports.

## Quick Start

1. Confirm the repo root and draft year.
2. Run the helper script:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py audit --draft-year 2025
```

3. If browser-assisted collection is needed, print the plan:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py browser-plan --draft-year 2025
```

4. If raw files are outside the repo, use the staging commands in the helper script.
5. Once the audit is green enough, run ETL and build the demo site.

## When To Use This Skill

Use this skill when the user asks to:

- prepare data for a recent draft-class demo
- load or validate HockeyDB / Elite Prospects source files
- run the single-class ETL, demo export, and readiness-report flow
- reduce manual file-placement work around raw inputs

Do not use this skill for model tuning, board evaluation, or frontend polish after the data package is already built.

## Workflow

### 1. Scaffold and Audit

Start with:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py scaffold --draft-year 2025
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py audit --draft-year 2025
```

This uses the project’s existing CLI/data helpers and prints the expected raw paths and next commands.

### 2. Stage Local Files Into The Repo

If the user already has files in `Downloads` or another folder, use the staging commands instead of asking them to rename paths manually.

Examples:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-draft-html \
  --draft-year 2025 \
  --source /path/to/nhl2025e.html

python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-eliteprospects-csv \
  --draft-year 2025 \
  --source /path/to/export.csv

python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-player-pages \
  --draft-year 2025 \
  --source-dir /path/to/player_pages_dir
```

### 3. Browser Collection When Needed

If files are not available locally and the session has browser capability, use the in-app browser skill `control-in-app-browser` to navigate, inspect, and assist with collection.

Read [references/browser-collection.md](references/browser-collection.md) when:

- the user wants browser-assisted collection
- authenticated downloads are involved
- you need to explain why the browser step still may require user confirmation

If the session is network-restricted, say so plainly and fall back to staging user-provided files.

Start by printing the collection plan:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py browser-plan --draft-year 2025
```

If the browser downloads files into a standard downloads folder, try:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-downloads --draft-year 2025
```

### 4. Run ETL And Build The Demo Readiness Package

Once the needed raw files are present:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py run-etl --draft-year 2025 --with-eliteprospects
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py build-demo --draft-year 2025
```

`build-demo` now calls the project `build-demo-readiness` command. It writes:

- `index.html`
- `board.csv`, `compare.csv`, `players.json`, `manifest.json`
- `reports/data_gaps/summary.md`
- `reports/modeling_sanity/summary.md`

### 5. Report Readiness Clearly

After ETL/demo build:

- summarize what was collected
- call out any missing player-page or EP coverage
- point to the built output directory and report summaries
- mention whether the class is merely ETL-ready or actually demo-strong

## Helper Script

Use `scripts/demo_data_workflow.py` for local deterministic actions:

- scaffold year layout
- audit current readiness
- print a browser collection plan with exact target paths
- stage raw files into expected repo paths
- try auto-staging likely files from a downloads folder
- run ETL
- build demo site and readiness reports

Prefer the script over retyping long commands when it covers the task.

## References

- For browser-assisted collection and caveats: [references/browser-collection.md](references/browser-collection.md)
