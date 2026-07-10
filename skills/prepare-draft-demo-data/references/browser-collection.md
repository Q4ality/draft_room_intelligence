# Browser Collection Notes

Use browser-assisted collection only when the session actually has browser/web capability. This skill is meant to reduce manual file choreography, but authenticated downloads can still require the user to click or sign in.

Start with:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py browser-plan --draft-year 2025
```

That prints the target repo paths, the inferred HockeyDB draft-page URL pattern, and the follow-up staging commands.

## Suggested Collection Order

1. Open the HockeyDB draft page for the target year.
2. Save or export the page HTML into the expected path for the repo.
3. Identify the featured players or collect the full set of player-page links.
4. Save player profile pages into the expected `player_pages/` directory.
5. Open Elite Prospects, complete sign-in if needed, and export the draft-year CSV.
6. Stage the export into the repo and validate it locally.

If downloaded files land in a normal downloads folder, try:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py stage-downloads --draft-year 2025
```

This can auto-stage a likely draft HTML file and a likely Elite Prospects CSV from `~/Downloads`.

## Practical Boundaries

- HockeyDB or Elite Prospects may rate-limit or block automation.
- Elite Prospects exports may require the user's authenticated account.
- The browser step may need user confirmation for file downloads.
- In network-restricted sessions, do not pretend this step is available. Say so plainly and fall back to staging local files.

## After Browser Collection

Once files exist locally, switch back to deterministic local commands:

```bash
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py audit --draft-year 2025
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py run-etl --draft-year 2025 --with-eliteprospects
python3 skills/prepare-draft-demo-data/scripts/demo_data_workflow.py build-demo --draft-year 2025
```
