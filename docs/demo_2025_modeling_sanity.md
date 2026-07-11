# 2025 Demo Modeling Sanity

Generated from:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-modeling \
  outputs/demo_2025_openstats_russian_nordic_cleanup \
  outputs/demo_2025_openstats_russian_nordic_cleanup_modeling \
  --top-n 40
```

## Snapshot

- Draft year: 2025
- Players: 224
- Dataset status: `strong`
- Average absolute board-vs-consensus movement: 9.9 slots
- Players moved 10+ slots: 89
- 10+ slot moves with high/medium evidence: 70

## What This Says

The current board is meaningfully different from simple consensus order, but it is not detached from consensus.

- Top 10 overlap with consensus: 5 of 10
- Top 25 overlap with consensus: 20 of 25
- Top 50 overlap with consensus: 43 of 50

That is a healthy demo posture: the system can change the conversation, especially inside a decision band, without pretending it has a fully independent outcome-validated 2025 forecast.

## Role Movement

| Role | Players | Avg Abs Move | Model Higher | Consensus Higher | Aligned | 10+ Moves With Usable Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| defense | 69 | 10.1 | 4 | 37 | 28 | 23 |
| forward | 131 | 10.0 | 47 | 27 | 57 | 41 |
| goalie | 24 | 8.8 | 9 | 5 | 10 | 6 |

Interpretation:

- The current board tends to be more aggressive on forwards than public consensus.
- Defensemen are more often consensus-higher, so the model is comparatively cautious there.
- Goalies move, but the movement is smaller and should remain tied to goalie-specific evidence depth.

## Largest Useful Demo Movements

| Move | Player | Role | Board | Consensus | Evidence | League | Why it matters |
| ---: | --- | --- | ---: | ---: | --- | --- | --- |
| 47 | Roman Luttsev | forward | 159 | 206 | high | MHL | Late-round model-favorite story with multi-league evidence. |
| 37 | Marco Mignosa | forward | 178 | 215 | medium | OHL | Late-round production story from a familiar CHL source family. |
| -36 | Max Psenicka | defense | 82 | 46 | high | WHL | Consensus is more aggressive despite adult/playoff context. |
| -35 | Theodor Hallquisth | defense | 87 | 52 | high | Sweden Jrs. | Nordic defense example where consensus remains higher. |
| 34 | Ethan Wyttenbach | forward | 110 | 144 | high | USHL | Model-favored American junior case. |
| -31 | Liam Pettersson | defense | 92 | 61 | high | Sweden Jrs. | Good Nordic cross-league caution example. |
| -31 | Kurban Limatov | defense | 98 | 67 | high | MHL | Russian defense case where consensus is more aggressive. |
| -28 | Will Horcoff | forward | 52 | 24 | high | NCAA | High-evidence player where the board is materially more cautious. |
| -26 | Sascha Boumedienne | defense | 54 | 28 | high | USHL | Defense caution story with strong evidence depth. |
| 20 | Jack Ivankovic | goalie | 38 | 58 | medium | OHL | Goalie-specific stat signal creates a model-higher discussion case. |

Positive movement means the board ranks the player higher than consensus. Negative movement means consensus ranks the player higher than the board.

## Demo Guidance

Use high/medium evidence movement cases as the main business demo examples. Low-evidence movement cases should be framed as source-coverage prompts, not as confident recommendations.

Good presentation sequence:

1. Show top-50 overlap to establish that the board remains anchored.
2. Show Roman Luttsev or Ethan Wyttenbach as model-favored review targets.
3. Show Max Psenicka or Sascha Boumedienne as consensus-favored caution cases.
4. Show Jack Ivankovic or Alexei Medvedev as a goalie-specific case.
5. Close by explaining that low-evidence movement feeds the data-gap workflow.

## Caveat

This is a recent-class sanity report. It evaluates demo board behavior against consensus, not future NHL outcomes. Historical validation still needs older draft classes with real outcome labels.
