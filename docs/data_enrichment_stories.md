# Data Enrichment Stories

Backlog stories for making the 2025 demo data business-relevant and for moving the platform toward repeatable multi-class modeling.

## Current Implementation Status

- Implemented: goalie-specific normalized stat columns, CHL goalie metric loading, goalie feature-table fields, demo export goalie fields, and row-level source provenance in player history.
- Implemented: recent-class validation warning when outcome-evaluation commands are run against datasets with all-zero NHL outcomes.
- Implemented: generic `enrich-open-stats-csv` bridge for cleaned open-source NCAA, USHL, Swedish, Finnish, Russian, or fallback web stat tables.
- Implemented: first curated priority source pack at `data/reference/demo_2025_priority_open_stats.csv`, covering USHL/USNTDP history for James Hagens, Logan Hensler, Sascha Boumedienne, Cullen Potter, and William Moore.
- Implemented: curated Russian, Nordic, and cleanup open-stat source packs for the 2025 demo, with the current strong package reaching 457 stat lines and 50 high-evidence players.
- Implemented: first presenter-ready demo storyline in `docs/demo_2025_presenter_script.md`.
- Still needed: league-specific collectors/parsers that produce the cleaned open-stats CSVs automatically from each source family.

## Story 1: NCAA And Richer USHL Histories

As a scout, I want NCAA, USNTDP, and USHL players to have real pre-draft stat histories, so top-board American players are not shown as low evidence just because the current adapter only has one row.

Why this matters:
- Current low-evidence top-board examples include James Hagens, Logan Hensler, Sascha Boumedienne, Cullen Potter, Jack Murtagh, Carter Amico, Conrad Fondrk, Shane Vansaghi, Charlie Cerrato, William Moore, Ben Kevan, and Charlie Trethewey.
- NCAA/USHL gaps hurt demo credibility because many high-value prospects are in this path.

Acceptance criteria:
- Add source adapter(s) for NCAA/USHL/USNTDP open stat pages or reliable cached exports. The generic `enrich-open-stats-csv` command can now load cleaned source CSVs while a source-specific collector is built.
- Capture regular-season and playoff/tournament rows when available.
- Preserve source URL and source type per row.
- Reduce low-evidence top-75 NCAA/USHL players by at least 50 percent in the 2025 demo snapshot.
- Add parser tests with saved HTML/CSV fixtures.

Implementation notes:
- Start with a small source matrix for NCAA, USHL, USNTDP, and major tournaments.
- Prefer official or stable public stat tables over broad web scraping.
- Keep a cache-first workflow so the ETL can run without live network access.
- Candidate fallback sources found during research: College Hockey Inc. tables referenced from NCAA season pages and conference-season pages.

## Story 2: Swedish And Finnish League Coverage

As a scout, I want Swedish and Finnish junior/adult histories normalized, so European prospects can be compared with CHL, USHL, NCAA, and Russian players.

Why this matters:
- Current low-evidence clusters include `Swe-Jr`, `SweHL`, `Swe-1`, `Sweden Jrs.`, `SM-liiga`, and `Finland Jr.`
- Adult exposure is an important signal, but current Swedish/Finnish histories are incomplete and inconsistently labeled.

Acceptance criteria:
- Add adapters or source-specific importers for SHL, HockeyAllsvenskan, J20 Nationell, Liiga, Mestis, and Finnish U20 where open data is available. The generic `enrich-open-stats-csv` command can ingest cleaned exports from these sources immediately.
- Normalize league labels into the existing league-standardization layer.
- Capture regular-season and playoff rows where available.
- Preserve adult-vs-junior competition classification.
- Show evidence-depth improvement for Swedish/Finnish players in the 2025 demo EDA.

Implementation notes:
- First target named 2025 demo players rather than every historical season.
- Add league alias tests before adding broad scoring logic.
- Keep adult-league weighting explicit and reviewable.
- Candidate fallback sources found during research: league season pages that reference SHL official statistics and Elite Prospects public league stat pages where accessible.

## Story 3: Russian League Histories

As a scout, I want KHL, VHL, and MHL histories represented correctly, so Russian prospects with multi-league exposure are not reduced to placeholder rows.

Why this matters:
- Alexander Zharovsky became much more credible once his Salavat/KHL and Tolpar/MHL history appeared.
- Remaining low-evidence clusters include `Rus-MHL`, `KHL`, and related Russian junior/adult paths.

Acceptance criteria:
- Identify open, stable source pages for KHL, VHL, and MHL player stats. The generic `enrich-open-stats-csv` command can ingest cleaned KHL/MHL/VHL exports while protected official sites are avoided.
- Add a source adapter that can load cached HTML/CSV and produce normalized season rows.
- Capture adult exposure, junior exposure, and playoffs separately.
- Improve at least the top Russian 2025 demo prospects from low to medium/high evidence where data exists.
- Add parser tests and a source-match report.

Implementation notes:
- Avoid relying on pages protected by challenge/anti-bot flows as the only source.
- Treat transliteration/name matching as a first-class risk and expose unmatched candidates.
- Keep manual match-map support for ambiguous Cyrillic/Latin names.
- Candidate fallback sources found during research: KHL season/league pages and third-party stat aggregators such as QuantHockey when official pages are blocked.

## Story 4: Goalie-Specific Stat Schema

As a goalie evaluator, I want goalie performance metrics stored separately from skater scoring, so goalie rankings are based on relevant evidence instead of games played only.

Why this matters:
- CHL goalie exposure is now loaded, but normalized stat rows only support skater-style goals/assists/points.
- Players like Joshua Ravensbergen, Jack Ivankovic, Lucas Beckman, Gabriel D'Aigle, and other 2025 goalies need SV%, GAA, shots, saves, minutes, wins/losses, and shutouts to tell a credible story.

Acceptance criteria:
- Extend the normalized schema with goalie stat fields. Done.
- Update CHL goalie parser to populate the new fields. Done.
- Update feature table generation to produce goalie-specific features. Done.
- Update demo export/detail view so goalie metrics appear without pretending they are skater production. Done.
- Add tests covering goalie rows, feature export, and demo export.

Implementation notes:
- Keep skater and goalie feature paths separate after the shared identity/league/exposure fields.
- Avoid using goalie points as a proxy for goalie quality.
- Use a simple first-pass goalie score only after coverage is validated.

## Story 5: Recent-Class Demo Score Versus Historical Validation Score

As a business user, I want the product to clearly separate recent-class demo ranking from historically validated predictive performance, so I do not mistake a 2025 showcase for proven model accuracy.

Why this matters:
- The 2025 class has no meaningful NHL outcomes yet.
- Current role-model evaluation runs, but all outcome labels are zero, so the metrics are not a valid validation result.

Acceptance criteria:
- Add explicit CLI/report labeling for recent-class demo analysis versus historical outcome validation. Partially done via CLI warning.
- Prevent or warn on outcome-evaluation commands when all outcomes are zero. Done.
- Add a demo-readiness report focused on evidence depth, source coverage, disagreement buckets, and showcase-player sanity checks.
- Add a historical validation path that uses older classes with real NHL outcomes.
- Update docs and demo copy so business users understand what is proven versus illustrative.

Implementation notes:
- This is partly product UX and partly analytics hygiene.
- Treat evidence-depth movement as the success metric for recent-class enrichment.
- Treat precision/lift/rank-correlation as historical-class validation metrics only.
