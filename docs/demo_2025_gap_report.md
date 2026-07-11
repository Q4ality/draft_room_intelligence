# 2025 Demo Data Gap Report

Generated from:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-gaps \
  outputs/demo_2025_openstats_russian_nordic_cleanup \
  outputs/demo_2025_openstats_russian_nordic_cleanup_gaps \
  --top-n 35
```

## Snapshot

- Draft year: 2025
- Players: 224
- Dataset status: `strong`
- Low-evidence players: 77

## Low-Evidence League Clusters

- Sweden Jrs.: 13
- MHL: 12
- USHL: 10
- OHL: 5
- Finland Jrs.: 5
- WHL: 4
- High School: 3
- QMJHL: 3
- Liiga: 3
- SHL: 3
- BCHL: 3
- NCAA: 2

## Priority Source Strategies

- Sweden SHL/J20: 7
- NCAA/USHL/USNTDP: 7
- Goalie stat source: 5
- European fallback source: 4
- Finland Liiga/U20: 3
- Russian goalie stats: 2
- US high-school/prep: 2
- CHL skater/playoff: 2
- Russian KHL/MHL/VHL: 2
- CHL goalie stats: 1

## Top Priority Players

| Priority | Player | Pos | Board | Consensus | League | Strategy | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Gabriel D'Aigle | G | 66 | 84 | QMJHL | CHL goalie stats | low evidence; model higher; single stat row; missing playoff signal |
| 2 | Arseni Radkov | G | 67 | 82 | MHL | Russian goalie stats | low evidence; model higher; single stat row; missing playoff signal |
| 3 | Kieren Dervin | C | 57 | 65 | High School | US high-school/prep | low evidence; model higher; single stat row; missing playoff signal |
| 4 | Stepan Hoch | L | 74 | 78 | Czech | European fallback source | low evidence; single stat row; missing playoff signal; adult exposure needs verification |
| 5 | Malte Vass | D | 71 | 76 | Sweden Jrs. | Sweden SHL/J20 | low evidence; single stat row; missing playoff signal |
| 6 | Vashek Blanar | D | 108 | 100 | Sweden Jrs. | Sweden SHL/J20 | low evidence; consensus higher; single stat row; missing playoff signal |
| 7 | Trenten Bennett | G | 95 | 99 | CCHL | Goalie stat source | low evidence; single stat row; missing playoff signal |
| 8 | Drew Schock | D | 111 | 101 | USHL | NCAA/USHL/USNTDP | low evidence; consensus higher; single stat row; missing playoff signal |
| 9 | Francesco Dell'Elce | D | 75 | 77 | NCAA | NCAA/USHL/USNTDP | low evidence; single stat row; missing playoff signal |
| 10 | Matous Kucharcik | C | 112 | 103 | Czech. Jr | European fallback source | low evidence; consensus higher; single stat row; missing playoff signal |

## Recommended Next Data Work

1. Close the highest-ranked low-evidence players that also have model/consensus disagreement.
2. Work by source family so each pass improves a visible cluster, not just one player.
3. Rebuild the demo and compare high/medium/low evidence movement after each pass.

## Practical Next Enrichment Passes

1. **Goalie pass:** Gabriel D'Aigle, Arseni Radkov, Trenten Bennett, Elijah Neuenschwander, Petteri Rimpinen, Ivan Tkach-Tkachenko.
2. **Sweden pass:** Malte Vass, Vashek Blanar, Michal Svrcek, Linus Funck, Viktor Klingsell, Wilson Bjorck, Max Westergard.
3. **USHL/NCAA pass:** Drew Schock, Francesco Dell'Elce, Zack Sharp, Adam Benak, L.J. Mooney, Asher Barnett, William Belle.
4. **European fallback pass:** Stepan Hoch, Matous Kucharcik, Maxim Schafer, David Rozsival.
5. **Finland pass:** Tomas Poletin, Petteri Rimpinen, Daniel Nieminen, Samuel Jung, Daniel Salonen.
