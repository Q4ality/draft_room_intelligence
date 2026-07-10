# Data Directory

This project uses a split between tracked reference/sample data and untracked local raw inputs.

## Tracked in Git

- `reference/` contains reusable lookup tables such as league context.
- `processed/pilot_2019/` contains the current normalized pilot sample used for tests, evaluation, and examples.

## Kept Local

- `raw/` is for HockeyDB HTML caches, Elite Prospects exports, and other source files we can regenerate or re-import.
- larger ad hoc processed datasets can live here temporarily while we decide whether they belong in git or external storage.

## Practical Rule

If a file is needed for reproducible examples, tests, or a small shared baseline, it can be tracked.
If it is proprietary, bulky, re-downloadable, or tied to one person's local workflow, keep it out of git.
