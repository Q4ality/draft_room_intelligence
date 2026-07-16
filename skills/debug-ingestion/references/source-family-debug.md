# Source-Family Debug Map

Use this map after identifying the affected family in `data/reference/ingestion_source_families.csv`.

## Elite Prospects PDF

Check:

- raw guide PDF under `data/raw/draftdata/`,
- parser output under `outputs/ep_pdf_*`,
- player/profile/stat tables,
- goalie stat fields and tool-grade extraction,
- page references in player detail evidence.

Common failures:

- partial page window only,
- profile rows extracted but stat rows missing,
- player names need manual match review,
- PDF evidence exists but demo board calibration underweights elite defense/goalie context.

## CHL

Check:

- cached official CHL source files under `data/raw/cache/chl_stats`,
- regular-season and playoff rows are separate,
- goalie tables use goalie metrics,
- team abbreviations normalize to stable team names.

Common failures:

- playoff-team pages accidentally treated as regular-season rows,
- abbreviated team names create duplicate rows,
- high-ranked CHL players remain low-evidence because playoff rows are missing.

## NCAA, USHL, And USNTDP

Check:

- source split between USHL, NTDP, NCAA, and international tournament rows,
- player age/draft-year alignment,
- multiple same-season leagues are preserved.

Common failures:

- curated pack exists but raw cache is missing,
- NTDP/USHL rows collapse into one generic USA row,
- source evidence is available but not mapped to the base player ID.

## Sweden And Finland

Check:

- adult and junior league classification,
- Liiga/Mestis/U20 and SHL/HockeyAllsvenskan/J20 row separation,
- playoffs and relegation/tournament rows where available.

Common failures:

- junior/adult exposure is misclassified,
- league aliases create duplicate rows,
- production is compared without league-strength context.

## Russia KHL, MHL, And VHL

Check:

- transliteration variants,
- KHL/VHL/MHL adult/junior context,
- playoff rows,
- goalie metrics for Russian goalies.

Common failures:

- official pages blocked, requiring cached/open alternatives,
- player appears under multiple English spellings,
- KHL short sample is overinterpreted without GP/sample weighting.

## Team Rosters

Check:

- snapshot date and season label,
- NHL-ready roster vs AHL/prospect pipeline split,
- U23 pipeline counts,
- position/role normalization.

Common failures:

- current assignments leak into historical preseason proxy,
- AHL candidates are treated as NHL locks,
- young high-end prospects are not counted as depth pressure.
