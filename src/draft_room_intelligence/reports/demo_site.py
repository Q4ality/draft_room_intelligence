"""Generate a self-contained HTML demo app from demo export data."""

from __future__ import annotations

import json
from pathlib import Path

from draft_room_intelligence.reports.demo_export import DemoExportBundle


def write_demo_site(output_dir: str | Path, bundle: DemoExportBundle) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    html_path = root / "index.html"
    html_path.write_text(render_demo_site(bundle), encoding="utf-8")
    return html_path


def render_demo_site(bundle: DemoExportBundle) -> str:
    payload = {
        "manifest": bundle.manifest,
        "boardRows": bundle.board_rows,
        "playerDetails": bundle.player_details,
        "compareRows": bundle.compare_rows,
    }
    data_json = json.dumps(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Draft Room Intelligence Demo</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --panel: #ffffff;
      --panel-2: #f8fafc;
      --text: #0f172a;
      --muted: #475569;
      --line: #dbe2ea;
      --accent: #0f766e;
      --accent-soft: #ccfbf1;
      --warn: #92400e;
      --warn-soft: #fef3c7;
      --danger: #991b1b;
      --danger-soft: #fee2e2;
      --shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    .app {{
      display: grid;
      grid-template-columns: 300px 1fr 420px;
      min-height: 100vh;
    }}
    .sidebar, .detail {{
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 20px;
    }}
    .detail {{
      border-right: 0;
      border-left: 1px solid var(--line);
      overflow: auto;
    }}
    .main {{
      padding: 20px;
      overflow: auto;
    }}
    h1, h2, h3, h4, p {{ margin: 0; }}
    .eyebrow {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      margin-bottom: 8px;
      letter-spacing: 0.04em;
    }}
    .title {{
      font-size: 24px;
      font-weight: 700;
      margin-bottom: 10px;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
      margin-bottom: 18px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }}
    .stat {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .stat-value {{
      font-size: 18px;
      font-weight: 700;
    }}
    .section {{
      margin-top: 18px;
    }}
    .section h3 {{
      font-size: 14px;
      margin-bottom: 10px;
    }}
    .field {{
      margin-bottom: 12px;
    }}
    .field label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    select, input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fff;
      color: var(--text);
      font-size: 14px;
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .toolbar-right {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 8px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--muted);
    }}
    .badge-strong {{
      background: var(--accent-soft);
      color: var(--accent);
      border-color: transparent;
    }}
    .badge-thin {{
      background: var(--warn-soft);
      color: var(--warn);
      border-color: transparent;
    }}
    button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      cursor: pointer;
    }}
    button.small {{
      padding: 6px 8px;
      font-size: 12px;
      border-radius: 6px;
    }}
    button.primary {{
      background: var(--text);
      color: #fff;
      border-color: var(--text);
    }}
    .table-wrap {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      background: var(--panel-2);
      color: var(--muted);
      font-weight: 600;
    }}
    tr:hover td {{
      background: #f8fbff;
    }}
    tr.selected td {{
      background: #eef6ff;
    }}
    .player-button {{
      color: var(--text);
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
    }}
    .taglist {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .tag {{
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 11px;
      background: var(--panel-2);
      color: var(--muted);
    }}
    .tag.model {{ background: var(--accent-soft); color: var(--accent); }}
    .tag.warn {{ background: var(--warn-soft); color: var(--warn); }}
    .tag.risk {{ background: var(--danger-soft); color: var(--danger); }}
    .tag.shortlist {{ background: #e0f2fe; color: #0c4a6e; }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0 18px;
    }}
    .detail-card {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
    }}
    .detail-card .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .detail-card .value {{
      font-weight: 700;
      font-size: 15px;
    }}
    .detail-list {{
      margin: 10px 0 0;
      padding-left: 18px;
      color: var(--text);
      line-height: 1.5;
      font-size: 14px;
    }}
    .history {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      margin-top: 10px;
    }}
    .history td, .history th {{
      font-size: 12px;
      padding: 8px 10px;
    }}
    .compare-panel {{
      margin-top: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .compare-head {{
      padding: 14px 16px;
      background: var(--panel-2);
      border-bottom: 1px solid var(--line);
    }}
    .compare-grid {{
      display: grid;
      grid-template-columns: 180px repeat(3, minmax(0, 1fr));
    }}
    .compare-grid > div {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      border-right: 1px solid var(--line);
      font-size: 13px;
    }}
    .compare-grid > div:nth-child(4n) {{
      border-right: 0;
    }}
    .compare-label {{
      color: var(--muted);
      background: var(--panel-2);
      font-weight: 600;
    }}
    .empty {{
      color: var(--muted);
      font-size: 14px;
      padding: 16px 0;
    }}
    .featured-list {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 8px;
    }}
    .featured-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
    }}
    .featured-item button {{
      flex: 0 0 auto;
    }}
    .row-actions {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 6px;
    }}
    .header-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 10px 0 12px;
    }}
    @media (max-width: 1200px) {{
      .app {{
        grid-template-columns: 280px 1fr;
      }}
      .detail {{
        grid-column: 1 / -1;
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
    }}
    @media (max-width: 900px) {{
      .app {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .detail {{
        border-top: 1px solid var(--line);
      }}
      .toolbar {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="eyebrow">Draft Room Intelligence</div>
      <div class="title">Single-Class Demo</div>
      <div class="subtitle">Draft-meeting workflow for one class: normalize the evidence, find disagreement, inspect the source trail, and export a review list.</div>
      <div class="stats">
        <div class="stat">
          <div class="stat-label">Draft Year</div>
          <div class="stat-value" id="stat-draft-year"></div>
        </div>
        <div class="stat">
          <div class="stat-label">Players</div>
          <div class="stat-value" id="stat-player-count"></div>
        </div>
        <div class="stat">
          <div class="stat-label">Dataset Status</div>
          <div class="stat-value" id="stat-dataset-status"></div>
        </div>
        <div class="stat">
          <div class="stat-label">Featured Disagreements</div>
          <div class="stat-value" id="stat-featured-count"></div>
        </div>
      </div>
      <div class="section">
        <h3>Filters</h3>
        <div class="field">
          <label for="filter-position">Position</label>
          <select id="filter-position"></select>
        </div>
        <div class="field">
          <label for="filter-league-family">League Family</label>
          <select id="filter-league-family"></select>
        </div>
        <div class="field">
          <label for="filter-competition">Competition Level</label>
          <select id="filter-competition"></select>
        </div>
        <div class="field">
          <label for="filter-disagreement">Disagreement</label>
          <select id="filter-disagreement"></select>
        </div>
        <div class="field">
          <label for="filter-evidence">Evidence Depth</label>
          <select id="filter-evidence"></select>
        </div>
        <div class="field">
          <label for="filter-search">Search</label>
          <input id="filter-search" type="text" placeholder="Player or league">
        </div>
      </div>
      <div class="section">
        <h3>Source Coverage</h3>
        <div id="source-coverage" class="taglist"></div>
      </div>
      <div class="section">
        <h3>Featured Disagreements</h3>
        <div id="featured-players" class="featured-list"></div>
      </div>
    </aside>
    <main class="main">
      <div class="toolbar">
        <div>
          <div class="eyebrow">Board</div>
          <div class="title">2025 Demo Workspace</div>
          <div class="subtitle">Use this board to focus the meeting on players where normalized evidence, role context, and public consensus tell different stories.</div>
        </div>
        <div class="toolbar-right">
          <div id="status-badge" class="badge"></div>
          <button id="export-shortlist">Export Shortlist CSV</button>
          <button id="clear-shortlist">Clear Shortlist</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width: 58px;">Rank</th>
              <th style="width: 220px;">Player</th>
              <th style="width: 70px;">Pos</th>
              <th style="width: 120px;">League</th>
              <th style="width: 88px;">Consensus</th>
              <th style="width: 88px;">Board</th>
              <th style="width: 110px;">Adjusted</th>
              <th style="width: 110px;">Adult</th>
              <th style="width: 110px;">Playoff</th>
              <th style="width: 190px;">Actions</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody id="board-body"></tbody>
        </table>
      </div>
      <div class="compare-panel">
        <div class="compare-head">
          <div class="eyebrow">Compare</div>
          <div class="title" style="font-size:18px;">Selected Players</div>
        </div>
        <div id="compare-content" class="empty" style="padding:16px;">Select up to three players for side-by-side comparison.</div>
      </div>
    </main>
    <aside class="detail">
      <div id="detail-empty" class="empty">Select a player to inspect the evidence, translation context, and review flags behind the ranking.</div>
      <div id="detail-content" style="display:none;">
        <div class="eyebrow">Player Detail</div>
        <div class="title" id="detail-name"></div>
        <div class="subtitle" id="detail-meta"></div>
        <div class="header-actions">
          <button id="detail-shortlist" class="small">Add to shortlist</button>
          <button id="detail-compare" class="small">Compare</button>
        </div>
        <div class="taglist" id="detail-badges" style="margin-bottom:12px;"></div>
        <div class="detail-grid" id="detail-grid"></div>
        <div class="section">
          <h3>Why Review</h3>
          <ul class="detail-list" id="detail-why-high"></ul>
        </div>
        <div class="section">
          <h3>Review Flags</h3>
          <ul class="detail-list" id="detail-risk-flags"></ul>
        </div>
        <div class="section">
          <h3>Pre-Draft History</h3>
          <table class="history">
            <thead>
              <tr>
                <th>Season</th>
                <th>League</th>
                <th>Team</th>
                <th>GP</th>
                <th>PTS</th>
                <th>Stage</th>
              </tr>
            </thead>
            <tbody id="detail-history"></tbody>
          </table>
        </div>
        <div class="section">
          <h3>Source Trace</h3>
          <div id="detail-sources" class="taglist"></div>
        </div>
      </div>
    </aside>
  </div>
  <script>
    const payload = {data_json};
    const boardRows = payload.boardRows;
    const playerDetails = Object.fromEntries(payload.playerDetails.map((item) => [item.player_id, item]));
    const shortlist = new Set();
    const compare = [];
    let selectedPlayerId = boardRows[0]?.player_id ?? null;

    function uniqueValues(key) {{
      return [...new Set(boardRows.map((row) => row[key]).filter(Boolean))].sort();
    }}

    function populateSelect(id, values, allLabel = "All") {{
      const select = document.getElementById(id);
      select.innerHTML = "";
      const all = document.createElement("option");
      all.value = "";
      all.textContent = allLabel;
      select.appendChild(all);
      for (const value of values) {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }}
    }}

    function initializeFilters() {{
      populateSelect("filter-position", uniqueValues("position"));
      populateSelect("filter-league-family", uniqueValues("primary_league_family"));
      populateSelect("filter-competition", uniqueValues("primary_competition_level"));
      populateSelect("filter-disagreement", uniqueValues("disagreement_bucket"));
      populateSelect("filter-evidence", uniqueValues("evidence_depth"));
    }}

    function applyFilters(rows) {{
      const position = document.getElementById("filter-position").value;
      const family = document.getElementById("filter-league-family").value;
      const level = document.getElementById("filter-competition").value;
      const disagreement = document.getElementById("filter-disagreement").value;
      const evidence = document.getElementById("filter-evidence").value;
      const search = document.getElementById("filter-search").value.trim().toLowerCase();
      return rows.filter((row) => {{
        if (position && row.position !== position) return false;
        if (family && row.primary_league_family !== family) return false;
        if (level && row.primary_competition_level !== level) return false;
        if (disagreement && row.disagreement_bucket !== disagreement) return false;
        if (evidence && row.evidence_depth !== evidence) return false;
        if (search) {{
          const haystack = `${{row.name}} ${{row.primary_league}} ${{row.primary_league_family}}`.toLowerCase();
          if (!haystack.includes(search)) return false;
        }}
        return true;
      }});
    }}

    function tagClass(label) {{
      if (label === "Model Higher") return "tag model";
      if (label === "Consensus Higher" || label === "Low Evidence") return "tag warn";
      if (label === "Adult-League") return "tag model";
      return "tag";
    }}

    function evidenceLabel(value) {{
      if (value === "high") return "High coverage";
      if (value === "medium") return "Usable coverage";
      if (value === "low") return "Needs coverage";
      return value || "Unknown";
    }}

    function renderBoard() {{
      const body = document.getElementById("board-body");
      body.innerHTML = "";
      const rows = applyFilters(boardRows);
      for (const row of rows) {{
        const tr = document.createElement("tr");
        if (row.player_id === selectedPlayerId) tr.classList.add("selected");
        const badgeLabels = row.badges ? row.badges.split("|").filter(Boolean) : [];
        tr.innerHTML = `
          <td>${{row.board_rank}}</td>
          <td>
            <div class="player-button" data-player-id="${{row.player_id}}">${{row.name}}</div>
            <div style="color:var(--muted); font-size:12px; margin-top:4px;">${{row.primary_league_family}}</div>
          </td>
          <td>${{row.position}}</td>
          <td>${{row.primary_league}}</td>
          <td>${{row.consensus_rank}}</td>
          <td>${{Number(row.board_score).toFixed(3)}}</td>
          <td>${{Number(row.adjusted_production_score).toFixed(3)}}</td>
          <td>${{Math.round(Number(row.adult_game_share) * 100)}}%</td>
          <td>${{Math.round(Number(row.playoff_game_share) * 100)}}%</td>
          <td>
            <div class="row-actions">
              <button class="small action-shortlist" data-player-id="${{row.player_id}}">${{shortlist.has(row.player_id) ? "Shortlisted" : "Shortlist"}}</button>
              <button class="small action-compare" data-player-id="${{row.player_id}}">${{compare.includes(row.player_id) ? "Compared" : "Compare"}}</button>
            </div>
          </td>
          <td>
            <div>${{row.short_reason}}</div>
            <div class="taglist" style="margin-top:6px;">${{badgeLabels.map((label) => `<span class="${{tagClass(label)}}">${{label}}</span>`).join("")}}</div>
          </td>
        `;
        tr.querySelector(".player-button").addEventListener("click", () => {{
          selectedPlayerId = row.player_id;
          renderBoard();
          renderDetail();
        }});
        tr.addEventListener("dblclick", () => toggleCompare(row.player_id));
        tr.querySelector(".action-shortlist").addEventListener("click", (event) => {{
          event.stopPropagation();
          toggleShortlist(row.player_id);
        }});
        tr.querySelector(".action-compare").addEventListener("click", (event) => {{
          event.stopPropagation();
          toggleCompare(row.player_id);
        }});
        body.appendChild(tr);
      }}
    }}

    function renderDetail() {{
      const detail = playerDetails[selectedPlayerId];
      const board = boardRows.find((row) => row.player_id === selectedPlayerId);
      const empty = document.getElementById("detail-empty");
      const content = document.getElementById("detail-content");
      if (!detail || !board) {{
        empty.style.display = "block";
        content.style.display = "none";
        return;
      }}
      empty.style.display = "none";
      content.style.display = "block";
      document.getElementById("detail-name").textContent = detail.header.name;
      document.getElementById("detail-meta").textContent =
        `${{detail.header.position}} · ${{board.primary_league}} · Consensus ${{detail.header.consensus_rank}} · Board ${{detail.header.board_rank}}`;
      const shortlistButton = document.getElementById("detail-shortlist");
      shortlistButton.textContent = shortlist.has(selectedPlayerId) ? "Remove from shortlist" : "Add to shortlist";
      const compareButton = document.getElementById("detail-compare");
      compareButton.textContent = compare.includes(selectedPlayerId) ? "Remove from compare" : "Compare";
      const badgeLabels = board.badges ? board.badges.split("|").filter(Boolean) : [];
      const badgeWrap = document.getElementById("detail-badges");
      badgeWrap.innerHTML = badgeLabels.map((label) => `<span class="${{tagClass(label)}}">${{label}}</span>`).join("");

      const metrics = [
        ["Board Score", Number(detail.summary.board_score).toFixed(3)],
        ["Model Score", Number(detail.summary.model_score).toFixed(3)],
        ["Adjusted PPG", Number(detail.summary.adjusted_ppg).toFixed(3)],
        ["Adult Share", `${{Math.round(detail.summary.adult_game_share * 100)}}%`],
        ["Playoff Share", `${{Math.round(detail.summary.playoff_game_share * 100)}}%`],
        ["Evidence", evidenceLabel(detail.summary.evidence_depth)],
      ];
      document.getElementById("detail-grid").innerHTML = metrics.map(([label, value]) => `
        <div class="detail-card">
          <div class="label">${{label}}</div>
          <div class="value">${{value}}</div>
        </div>
      `).join("");
      document.getElementById("detail-why-high").innerHTML = detail.why_high.map((item) => `<li>${{item}}</li>`).join("");
      document.getElementById("detail-risk-flags").innerHTML = detail.risk_flags.map((item) => `<li>${{item}}</li>`).join("");
      document.getElementById("detail-history").innerHTML = detail.pre_draft_history.map((row) => `
        <tr>
          <td>${{row.season}}</td>
          <td>${{row.league}}</td>
          <td>${{row.team}}</td>
          <td>${{row.games}}</td>
          <td>${{row.points}}</td>
          <td>${{row.regular_season ? "Regular" : "Playoff"}}</td>
        </tr>
      `).join("");
      document.getElementById("detail-sources").innerHTML = detail.sources.map((source) => `<span class="tag">${{source.source}}</span>`).join("");
    }}

    function toggleShortlist(playerId) {{
      if (shortlist.has(playerId)) {{
        shortlist.delete(playerId);
      }} else {{
        shortlist.add(playerId);
      }}
      renderBoard();
      renderDetail();
      renderManifest();
    }}

    function toggleCompare(playerId) {{
      const index = compare.indexOf(playerId);
      if (index >= 0) {{
        compare.splice(index, 1);
      }} else if (compare.length < 3) {{
        compare.push(playerId);
      }} else {{
        compare.shift();
        compare.push(playerId);
      }}
      renderCompare();
      renderBoard();
      renderDetail();
    }}

    function renderCompare() {{
      const container = document.getElementById("compare-content");
      if (!compare.length) {{
        container.className = "empty";
        container.textContent = "Select up to three players for side-by-side comparison.";
        return;
      }}
      const rows = compare.map((id) => boardRows.find((row) => row.player_id === id)).filter(Boolean);
      const fields = [
        ["Player", "name"],
        ["Position", "position"],
        ["Consensus Rank", "consensus_rank"],
        ["Board Rank", "board_rank"],
        ["Board Score", "board_score"],
        ["Adjusted Score", "adjusted_production_score"],
        ["Role Percentile", "role_percentile"],
        ["Primary League", "primary_league"],
        ["Average League Weight", "average_league_weight"],
        ["Adult Share", "adult_game_share"],
        ["Playoff Share", "playoff_game_share"],
        ["Evidence", "evidence_depth"],
      ];
      let html = '<div class="compare-grid">';
      for (const [label, key] of fields) {{
        html += `<div class="compare-label">${{label}}</div>`;
        for (let i = 0; i < 3; i += 1) {{
          const row = rows[i];
          let value = row ? row[key] : "";
          if (row && ["board_score", "adjusted_production_score", "role_percentile", "average_league_weight"].includes(key)) {{
            value = Number(value).toFixed(3);
          }}
          if (row && ["adult_game_share", "playoff_game_share"].includes(key)) {{
            value = `${{Math.round(Number(value) * 100)}}%`;
          }}
          html += `<div>${{value || "—"}}</div>`;
        }}
      }}
      html += "</div>";
      container.className = "";
      container.innerHTML = html;
    }}

    function exportShortlist() {{
      const selected = boardRows.filter((row) => shortlist.has(row.player_id));
      const rows = selected.length ? selected : boardRows.filter((row) => compare.includes(row.player_id));
      if (!rows.length) {{
        alert("Add players to the shortlist or compare set first.");
        return;
      }}
      const columns = ["player_id", "name", "board_rank", "consensus_rank", "board_score", "short_reason", "risk_note"];
      const csv = [
        columns.join(","),
        ...rows.map((row) => columns.map((column) => `"${{String(row[column] ?? "").replaceAll('"', '""')}}"`).join(",")),
      ].join("\\n");
      const blob = new Blob([csv], {{ type: "text/csv;charset=utf-8" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `draft-room-shortlist-${{payload.manifest.draft_year || "demo"}}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    }}

    function renderManifest() {{
      document.getElementById("stat-draft-year").textContent = payload.manifest.draft_year ?? "—";
      document.getElementById("stat-player-count").textContent = payload.manifest.player_count ?? 0;
      document.getElementById("stat-dataset-status").textContent = payload.manifest.dataset_status;
      document.getElementById("stat-featured-count").textContent = shortlist.size || payload.manifest.featured_player_ids.length;
      const status = document.getElementById("status-badge");
      status.textContent = `Dataset: ${{payload.manifest.dataset_status}} · Shortlist: ${{shortlist.size}}`;
      status.className = `badge ${{payload.manifest.dataset_status === "strong" ? "badge-strong" : payload.manifest.dataset_status === "thin" ? "badge-thin" : ""}}`;
      const sources = document.getElementById("source-coverage");
      sources.innerHTML = Object.entries(payload.manifest.source_counts).map(([key, value]) => `<span class="tag">${{key}} · ${{value}}</span>`).join("");
      const featured = document.getElementById("featured-players");
      featured.innerHTML = payload.manifest.featured_player_ids.map((playerId) => {{
        const row = boardRows.find((item) => item.player_id === playerId);
        if (!row) return "";
        return `
          <div class="featured-item">
            <div>
              <div style="font-size:13px; font-weight:600;">${{row.name}}</div>
              <div style="font-size:12px; color:var(--muted);">Consensus delta ${{row.consensus_delta}}</div>
            </div>
            <button class="small featured-open" data-player-id="${{row.player_id}}">Open</button>
          </div>
        `;
      }}).join("");
      featured.querySelectorAll(".featured-open").forEach((button) => {{
        button.addEventListener("click", () => {{
          selectedPlayerId = button.dataset.playerId;
          renderBoard();
          renderDetail();
        }});
      }});
    }}

    function bindEvents() {{
      for (const id of ["filter-position", "filter-league-family", "filter-competition", "filter-disagreement", "filter-evidence", "filter-search"]) {{
        document.getElementById(id).addEventListener("input", renderBoard);
      }}
      document.getElementById("export-shortlist").addEventListener("click", exportShortlist);
      document.getElementById("clear-shortlist").addEventListener("click", () => {{
        shortlist.clear();
        compare.splice(0, compare.length);
        renderCompare();
        renderBoard();
        renderDetail();
        renderManifest();
      }});
      document.getElementById("detail-shortlist").addEventListener("click", () => {{
        if (selectedPlayerId) toggleShortlist(selectedPlayerId);
      }});
      document.getElementById("detail-compare").addEventListener("click", () => {{
        if (selectedPlayerId) toggleCompare(selectedPlayerId);
      }});
    }}

    initializeFilters();
    renderManifest();
    bindEvents();
    renderBoard();
    renderDetail();
    renderCompare();
  </script>
</body>
</html>
"""
