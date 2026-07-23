# Demo Data Gap Report

## Snapshot

- Draft year: 2025
- Players: 224
- Dataset status: `strong`
- Baseline: `sha256:25358c86d273aab7330ba94f3a18c1d7330cff9c005d873f90515e9c6d3263c8`
- Low-evidence players: 16

## Low-Evidence League Clusters

- MHL: 4
- BCHL: 3
- NCAA: 2
- Sweden Jrs.: 2
- OHL: 1
- Finland Jrs.: 1
- Switzerland Jrs.: 1
- High School: 1
- WHL: 1

## Priority Source Strategies

- Open-stats fallback: 3
- Russian goalie stats: 3
- NCAA/USHL/USNTDP: 2
- Sweden SHL/J20: 2
- CHL skater/playoff: 2
- Finland Liiga/U20: 1
- European fallback source: 1
- US high-school/prep: 1
- Russian KHL/MHL/VHL: 1

## Top Priority Players

| Priority | Player | Pos | Board | Consensus | League | Strategy | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Francesco Dell'Elce | D | 91 | 77 | NCAA | NCAA/USHL/USNTDP | low evidence; consensus higher; single stat row; playoff source unavailable; source family: NCAA/USHL/USNTDP |
| 2 | Vashek Blanar | D | 143 | 100 | Sweden Jrs. | Sweden SHL/J20 | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Sweden SHL/J20 |
| 3 | Parker Holmes | L | 154 | 107 | OHL | CHL skater/playoff | low evidence; consensus higher; single stat row; no playoff appearance found; source family: CHL skater/playoff |
| 4 | Zack Sharp | D | 166 | 124 | NCAA | NCAA/USHL/USNTDP | low evidence; consensus higher; single stat row; playoff source unavailable; source family: NCAA/USHL/USNTDP |
| 5 | Max Heise | C | 192 | 150 | BCHL | Open-stats fallback | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Open-stats fallback |
| 6 | Ilya Kanarsky | G | 218 | 194 | MHL | Russian goalie stats | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Russian goalie stats |
| 7 | Samuel Jung | R | 202 | 166 | Finland Jrs. | Finland Liiga/U20 | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Finland Liiga/U20 |
| 8 | Yevgeni Prokhorov | G | 222 | 199 | MHL | Russian goalie stats | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Russian goalie stats |
| 9 | Ludvig Johnson | D | 206 | 174 | Switzerland Jrs. | European fallback source | low evidence; consensus higher; single stat row; playoff source unavailable; source family: European fallback source |
| 10 | Sigge Holmgren | D | 210 | 178 | Sweden Jrs. | Sweden SHL/J20 | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Sweden SHL/J20 |
| 11 | Aidan Lane | R | 211 | 176 | High School | US high-school/prep | low evidence; consensus higher; single stat row; playoff source unavailable; source family: US high-school/prep |
| 12 | Jeremy Loranger | LWRW | 207 | 198 | BCHL | Open-stats fallback | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Open-stats fallback |
| 13 | Kale Dach | C | 212 | 201 | BCHL | Open-stats fallback | low evidence; consensus higher; single stat row; playoff source unavailable; source family: Open-stats fallback |
| 14 | Alexander Weiermair | C | 215 | 186 | WHL | CHL skater/playoff | low evidence; consensus higher; single stat row; no playoff appearance found; source family: CHL skater/playoff |
| 15 | Yan Matveiko | L | 223 | 211 | MHL | Russian KHL/MHL/VHL | low evidence; consensus higher; single stat row; source family: Russian KHL/MHL/VHL |
| 16 | Yegor Midlak | G | 224 | 224 | MHL | Russian goalie stats | low evidence; single stat row; playoff source unavailable; source family: Russian goalie stats |

## Recommended Next Data Work

1. Close the highest-ranked low-evidence players that also have model/consensus disagreement.
2. Work by source family so each pass improves a visible cluster, not just one player.
3. Rebuild the demo and compare high/medium/low evidence movement after each pass.
