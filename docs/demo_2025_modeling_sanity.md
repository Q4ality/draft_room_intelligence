# 2025 Demo Modeling Sanity

Generated from:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-modeling \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/modeling_sanity \
  --top-n 40
```

## Snapshot

- Draft year: 2025
- Players: 224
- Dataset status: `strong`
- Average absolute board-vs-consensus movement: 13.8 slots
- Players moved 10+ slots: 135
- 10+ slot moves with high/medium evidence: 116

## What This Says

The current board is meaningfully different from simple consensus order, but it is not detached from consensus.

- Top 10 overlap with consensus: 9 of 10
- Top 25 overlap with consensus: 25 of 25
- Top 50 overlap with consensus: 50 of 50

That is a safer business-demo posture than the earlier scoring-forward-heavy board: the top of the board remains anchored to consensus while the detail view still explains model, EP evidence, and team-fit differences.

## Score Semantics

- `model_score` is still the most production/stat-sensitive score. It can be lower for injury-shortened samples or defense/goalie profiles.
- `board_score` is the demo board order. It blends model output, consensus rank, EP guide evidence, and role-aware calibration.
- `team_adjusted_score` applies NHL/AHL organization context on top of the board score.
- Matthew Schaefer is the important calibration check: he remains top-tier by `board_score` because consensus, EP evidence, defense role rank, and NYI fit outweigh the shortened 19-game captured sample.

## Role Movement

| Role | Players | Avg Abs Move | Model Higher | Consensus Higher | Aligned | 10+ Moves With Usable Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| defense | 69 | 16.0 | 2 | 48 | 19 | 39 |
| forward | 131 | 12.7 | 13 | 66 | 52 | 67 |
| goalie | 24 | 13.2 | 0 | 15 | 9 | 10 |

Interpretation:

- The calibrated board is no longer strongly biased toward scoring forwards at the top.
- Defense and goalie profiles are more consensus-protected, especially when production evidence is shortened or role-specific.
- Remaining large movements should be interpreted as review/data-gap prompts unless they have high or medium evidence.

## Largest Useful Demo Movements

| Move | Player | Role | Board | Consensus | Evidence | League | Why it matters |
| ---: | --- | --- | ---: | ---: | --- | --- | --- |
| -45 | Michal Svrcek | forward | 164 | 119 | low | SHL | Low-evidence consensus-higher caution case. |
| -44 | Parker Holmes | forward | 151 | 107 | low | OHL | Low-evidence team-fit/source-coverage prompt. |
| -43 | Zack Sharp | defense | 167 | 124 | low | NCAA | Low-evidence consensus-higher defense case. |
| -38 | Vashek Blanar | defense | 138 | 100 | low | Sweden Jrs. | Nordic source-coverage caution case. |
| -38 | Max Heise | forward | 188 | 150 | low | BCHL | Low-evidence consensus-higher case. |
| -33 | Artyom Gonchar | defense | 122 | 89 | high | MHL | High-evidence Russian defense disagreement. |
| -33 | Anthony Allain-Samake | defense | 129 | 96 | high | USHL | High-evidence defense caution case. |
| -33 | Matous Kucharcik | forward | 136 | 103 | high | U20 | Multi-league consensus-higher case. |
| -33 | Ilyas Magomedsultanov | defense | 148 | 115 | high | MHL | Russian defense disagreement with production signal. |
| 33 | Ryan Rucinski | forward | 186 | 219 | high | USHL | Late-round model-higher review candidate. |

Positive movement means the board ranks the player higher than consensus. Negative movement means consensus ranks the player higher than the board.

## Demo Guidance

Use high/medium evidence movement cases as the main business demo examples. Low-evidence movement cases should be framed as source-coverage prompts, not as confident recommendations.

Good presentation sequence:

1. Show top-50 overlap to establish that the board remains anchored.
2. Show Matthew Schaefer as the score-semantics example: model lower, board top-tier, team fit strong.
3. Show Artyom Gonchar or Anthony Allain-Samake as high-evidence consensus-higher caution cases.
4. Show Pyotr Andreyanov or Alexei Medvedev as goalie-specific evidence cases.
5. Close by explaining that low-evidence movement feeds the data-gap workflow.

## Caveat

This is a recent-class sanity report. It evaluates demo board behavior against consensus, not future NHL outcomes. Historical validation still needs older draft classes with real outcome labels.
