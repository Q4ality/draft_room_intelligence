# 2025 Demo Data Gap Report

Generated from:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-demo-gaps \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf \
  outputs/demo_2025_openstats_russian_nordic_cleanup_ep_pdf/reports/data_gaps \
  --top-n 35
```

## Snapshot

- Draft year: 2025
- Players: 224
- Dataset status: `strong`
- Low-evidence players: 27

## Low-Evidence League Clusters

- WHL: 4
- MHL: 4
- OHL: 3
- Sweden Jrs.: 3
- BCHL: 3
- NCAA: 2
- Finland Jrs.: 2
- QMJHL: 1
- USHL: 1
- SHL: 1
- Switzerland Jrs.: 1
- High School: 1

## Priority Source Strategies

- CHL skater/playoff: 7
- Sweden SHL/J20: 5
- NCAA/USHL/USNTDP: 3
- Open-stats fallback: 3
- Russian goalie stats: 3
- CHL goalie stats: 1
- Goalie stat source: 1
- Finland Liiga/U20: 1
- European fallback source: 1
- US high-school/prep: 1
- Russian KHL/MHL/VHL: 1

## Top Priority Players

| Priority | Player | Pos | Board | Consensus | League | Strategy | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Carter Bear | LW | 7 | 8 | WHL | CHL skater/playoff | low evidence; single stat row; missing playoff signal |
| 2 | Lynden Lakovic | LWRW | 10 | 14 | WHL | CHL skater/playoff | low evidence; single stat row; missing playoff signal |
| 3 | Francesco Dell'Elce | D | 99 | 77 | NCAA | NCAA/USHL/USNTDP | low evidence; consensus higher; single stat row; missing playoff signal |
| 4 | Gabriel D'Aigle | G | 85 | 84 | QMJHL | CHL goalie stats | low evidence; single stat row; missing playoff signal |
| 5 | Adam Benak | RWC | 119 | 102 | USHL | NCAA/USHL/USNTDP | low evidence; consensus higher; single stat row; missing playoff signal |
| 6 | Vashek Blanar | D | 138 | 100 | Sweden Jrs. | Sweden SHL/J20 | low evidence; consensus higher; single stat row; missing playoff signal |
| 7 | Quinn Beauchesne | D | 98 | 91 | OHL | CHL skater/playoff | low evidence; single stat row; missing playoff signal |
| 8 | Michal Svrcek | L | 164 | 119 | SHL | Sweden SHL/J20 | low evidence; consensus higher; single stat row; missing playoff signal; adult exposure needs verification |
| 9 | Parker Holmes | L | 151 | 107 | OHL | CHL skater/playoff | low evidence; consensus higher; single stat row; missing playoff signal |
| 10 | Zack Sharp | D | 167 | 124 | NCAA | NCAA/USHL/USNTDP | low evidence; consensus higher; single stat row; missing playoff signal |

## Recommended Next Data Work

1. Close the highest-ranked low-evidence players that also have model/consensus disagreement.
2. Work by source family so each pass improves a visible cluster, not just one player.
3. Rebuild the demo and compare high/medium/low evidence movement after each pass.

## Practical Next Enrichment Passes

1. **CHL cleanup pass:** Carter Bear, Lynden Lakovic, Quinn Beauchesne, Parker Holmes, Luke Vlooswyk, Alexander Weiermair, Charlie Paquette.
2. **USHL/NCAA pass:** Francesco Dell'Elce, Adam Benak, Zack Sharp.
3. **Sweden pass:** Vashek Blanar, Michal Svrcek, Gustav Sjoqvist, Sigge Holmgren, Jakob Leander.
4. **Goalie pass:** Gabriel D'Aigle, Daniel Salonen, Ilya Kanarsky, Yevgeni Prokhorov, Yegor Midlak.
5. **Open-stats fallback pass:** Max Heise, Jeremy Loranger, Kale Dach.
