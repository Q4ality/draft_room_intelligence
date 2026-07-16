---
name: validate-change
description: Choose and run focused validation for draft-room-intelligence changes. Use after editing code, ETL, demo exports, reports, skills, docs, source manifests, modeling logic, ranking calibration, or team-fit analytics; also use before committing or syncing repositories when the right test/report commands are not obvious.
---

# Validate Change

Use this skill to select the smallest useful validation set for the change. Prefer targeted checks over broad expensive runs, but do not skip acceptance gates for demo, ingestion, or scoring changes.

## Workflow

1. Inspect `git status --short` and identify changed files.
2. Classify the change area:
   - code/report module,
   - demo/data export,
   - ingestion/source-family,
   - modeling/scoring/team-fit,
   - docs/skill/process,
   - sync/commit only.
3. Read the relevant section of `references/check-matrix.md`.
4. Run the focused checks that match the changed files.
5. Always run `git diff --check` before commit.
6. Summarize results with pass/fail/unavailable, not full logs.

## Required Baseline

For any change:

```bash
git status --short
git diff --check
```

For Python code changes:

```bash
python3 -m compileall src/draft_room_intelligence
```

Run targeted pytest only if `pytest` is available in the active environment. If it is missing, report that explicitly and rely on compile/smoke checks.

## Output Contract

Report:

- changed areas validated,
- commands run,
- pass/fail/unavailable status,
- important failures or blockers,
- remaining risk.

Do not paste full command output unless the failure detail is necessary.

## References

- Read `references/check-matrix.md` for the command matrix by change area.
