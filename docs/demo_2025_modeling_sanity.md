# Demo Modeling Sanity Report

## Snapshot

- Draft year: 2025
- Players: 224
- Dataset status: `strong`
- Baseline: `sha256:25358c86d273aab7330ba94f3a18c1d7330cff9c005d873f90515e9c6d3263c8`
- Average absolute board-vs-consensus movement: 14.3 slots
- Players moved 10+ slots: 136
- 10+ slot moves with high/medium evidence: 122

## Top-N Overlap With Consensus

- Top 10: 9 shared players
- Top 25: 25 shared players
- Top 50: 50 shared players

## Disagreement Buckets

- consensus_higher: 127
- aligned: 76
- model_higher: 21

## Role Movement

| Role | Players | Avg Abs Move | Model Higher | Consensus Higher | Aligned | 10+ Moves With Usable Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| defense | 69 | 16.2 | 1 | 49 | 19 | 40 |
| forward | 131 | 12.8 | 20 | 61 | 50 | 68 |
| goalie | 24 | 17.2 | 0 | 17 | 7 | 14 |

## Largest Board Movements

| Move | Player | Role | Board | Consensus | Evidence | League | Reason |
| ---: | --- | --- | ---: | ---: | --- | --- | --- |
| -47 | Parker Holmes | forward | 154 | 107 | low | OHL | Stronger competition context, Consensus is more aggressive |
| -43 | Vashek Blanar | defense | 143 | 100 | low | Sweden Jrs. | Consensus is more aggressive |
| -42 | Zack Sharp | defense | 166 | 124 | low | NCAA | Stronger competition context, Consensus is more aggressive |
| -42 | Max Heise | forward | 192 | 150 | low | BCHL | Consensus is more aggressive |
| -37 | Artyom Gonchar | defense | 126 | 89 | high | MHL | EP guide grades add scouting context, Production stands out within role |
| -37 | Ilyas Magomedsultanov | defense | 152 | 115 | high | MHL | EP guide grades add scouting context, Production stands out within role |
| -36 | Samuel Jung | forward | 202 | 166 | low | Finland Jrs. | Consensus is more aggressive |
| 35 | Nolan Roed | forward | 179 | 214 | high | USHL | EP guide grades add scouting context, Playoff sample adds pressure context |
| 35 | Jacob Cloutier | forward | 185 | 220 | high | OHL | EP guide grades add scouting context, Stronger competition context |
| -35 | Aidan Lane | forward | 211 | 176 | low | High School | Consensus is more aggressive |
| -34 | Samuel Meloche | goalie | 150 | 116 | high | QMJHL | EP guide grades add scouting context, Goalie stat signal available |
| -33 | Asher Barnett | defense | 164 | 131 | medium | USHL | EP guide grades add scouting context, Consensus is more aggressive |
| 33 | Marco Mignosa | forward | 182 | 215 | high | OHL | Stronger competition context, Playoff sample adds pressure context |
| -32 | Lirim Amidovski | forward | 116 | 84 | high | OHL | EP guide grades add scouting context, Stronger competition context |
| -32 | Petteri Rimpinen | goalie | 132 | 100 | high | Liiga | EP guide grades add scouting context, Stronger competition context |

## Interpretation

- This is a recent-class demo sanity check, not outcome validation.
- The current board is meaningfully different from pure consensus, but still evidence-weighted.
- High/medium evidence movement cases are the safest stories to present.
- Low-evidence movement cases should be treated as data-gap prompts before business demos.
