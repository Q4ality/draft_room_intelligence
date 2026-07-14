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
    .scouting-panel {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin-top: 10px;
    }}
    .tool-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 10px;
    }}
    .tool-grade {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
    }}
    .tool-grade .tool {{
      color: var(--muted);
      font-size: 11px;
      text-transform: capitalize;
      margin-bottom: 2px;
    }}
    .tool-grade .grade {{
      font-weight: 700;
      font-size: 18px;
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
    .story-role {{
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 3px;
    }}
    .story-hook {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      margin-top: 3px;
    }}
    .demo-actions {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      margin-top: 8px;
    }}
    .source-link {{
      color: var(--accent);
      font-weight: 600;
      text-decoration: none;
    }}
    .source-link:hover {{
      text-decoration: underline;
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
        <h3>Demo Mode</h3>
        <div class="demo-actions">
          <button id="load-demo-stories" class="primary">Load Story Shortlist</button>
          <button id="load-demo-compare">Compare First Three Stories</button>
        </div>
      </div>
      <div class="section">
        <h3>Team View</h3>
        <select id="team-view-select" style="width:100%; margin-bottom:10px;"></select>
        <div id="team-view-summary" style="font-size:13px; line-height:1.45; margin-bottom:10px;"></div>
        <div id="team-view-gaps" class="featured-list" style="margin-bottom:10px;"></div>
        <div id="team-view-matches" class="featured-list"></div>
      </div>
      <div class="section">
        <h3>Guided Stories</h3>
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
          <button id="export-summary">Export Summary HTML</button>
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
              <th style="width: 96px;">Team</th>
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
        <div class="section" id="detail-stat-evidence-section">
          <h3>Prospect Stats Evidence</h3>
          <div class="scouting-panel">
            <div class="tool-grid" id="detail-stat-evidence"></div>
            <div class="taglist" id="detail-stat-evidence-tags" style="margin-top:10px;"></div>
          </div>
        </div>
        <div class="section" id="detail-team-fit-section" style="display:none;">
          <h3>Team Fit</h3>
          <div class="scouting-panel">
            <select id="detail-team-select" style="width:100%; margin-bottom:10px;"></select>
            <div class="taglist" id="detail-team-fit-tags" style="margin-bottom:10px;"></div>
            <div id="detail-team-info" style="font-size:13px; line-height:1.45; margin-bottom:10px;"></div>
            <div class="tool-grid" id="detail-team-fit-components" style="margin-bottom:10px;"></div>
            <div id="detail-team-fit-reason" style="font-size:14px; line-height:1.45;"></div>
          </div>
        </div>
        <div class="section" id="detail-scouting-section" style="display:none;">
          <h3>Elite Prospects Guide</h3>
          <div class="scouting-panel">
            <div id="detail-scouting-summary" style="font-size:14px; line-height:1.45;"></div>
            <div class="taglist" id="detail-scouting-tags" style="margin-top:10px;"></div>
            <div class="tool-grid" id="detail-tool-grades"></div>
          </div>
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
                <th>Production</th>
                <th>Stage</th>
                <th>Source</th>
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
    const demoStories = payload.manifest.demo_story_players || [];
    const shortlist = new Set();
    const compare = [];
    const selectedTeamByPlayer = new Map();
    const teamViews = payload.manifest.team_views || [];
    let selectedTeamViewId = teamViews[0]?.team_id || "";
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
      if (label === "Adult Sample" || label === "Playoff Sample" || label === "EP Elite Tools" || label === "Strong Team Fit") return "tag model";
      if (label === "Adult Exposure") return "tag warn";
      return "tag";
    }}

    function evidenceLabel(value) {{
      if (value === "high") return "High coverage";
      if (value === "medium") return "Usable coverage";
      if (value === "low") return "Needs coverage";
      return value || "Unknown";
    }}

    function percent(value) {{
      return `${{Math.round(Number(value || 0) * 100)}}%`;
    }}

    function decimalStat(value, digits) {{
      const numeric = Number(value || 0);
      if (!numeric) return "n/a";
      return numeric.toFixed(digits);
    }}

    function historyProductionLabel(row) {{
      if (row.save_percentage || row.goals_against_average) {{
        return `${{decimalStat(row.save_percentage, 3)}} / ${{decimalStat(row.goals_against_average, 2)}}`;
      }}
      return row.points ?? "";
    }}

    function adultSampleLabel(row) {{
      const tier = row.adult_sample_tier || "none";
      if (tier === "none") return "none";
      return `${{tier}} · ${{percent(row.adult_game_share)}}`;
    }}

    function storyRows() {{
      const storyIds = demoStories.map((story) => story.player_id);
      return storyIds.map((id) => boardRows.find((row) => row.player_id === id)).filter(Boolean);
    }}

    function sourceLabel(row) {{
      const source = row.source || "unknown";
      const id = row.source_id ? ` · ${{row.source_id}}` : "";
      if (row.source_url) {{
        return `<a class="source-link" href="${{row.source_url}}" target="_blank" rel="noopener noreferrer">${{source}}</a>${{id}}`;
      }}
      return `${{source}}${{id}}`;
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function selectedExportRows() {{
      const selected = boardRows.filter((row) => shortlist.has(row.player_id));
      return selected.length ? selected : boardRows.filter((row) => compare.includes(row.player_id));
    }}

    function storyForPlayer(playerId) {{
      return demoStories.find((story) => story.player_id === playerId);
    }}

    function downloadText(filename, content, mimeType) {{
      const blob = new Blob([content], {{ type: mimeType }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
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
          <td>
            <div>${{Number(row.team_adjusted_score || row.board_score).toFixed(3)}}</div>
            <div style="color:var(--muted); font-size:11px;">${{row.team_fit_need || ""}}</div>
          </td>
          <td>${{Number(row.adjusted_production_score).toFixed(3)}}</td>
          <td>${{adultSampleLabel(row)}}</td>
          <td>${{percent(row.playoff_game_share)}}</td>
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
        ["Team Score", Number(detail.summary.team_adjusted_score || detail.summary.board_score).toFixed(3)],
        ["Model Score", Number(detail.summary.model_score).toFixed(3)],
        ["EP Tools", percent(detail.summary.ep_tool_score || 0)],
        ["Adjusted PPG", Number(detail.summary.adjusted_ppg).toFixed(3)],
        ["Adult Share", percent(detail.summary.adult_game_share)],
        ["Playoff Share", percent(detail.summary.playoff_game_share)],
        ["Adult Evidence", percent(board.adult_evidence_weight)],
        ["Playoff Evidence", percent(board.playoff_evidence_weight)],
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
      renderStatEvidence(detail);
      renderTeamFit(detail);
      renderScouting(detail);
      document.getElementById("detail-history").innerHTML = detail.pre_draft_history.map((row) => `
        <tr>
          <td>${{row.season}}</td>
          <td>${{row.league}}</td>
          <td>${{row.team}}</td>
          <td>${{row.games}}</td>
          <td>${{historyProductionLabel(row)}}</td>
          <td>${{row.regular_season ? "Regular" : "Playoff"}}</td>
          <td>${{sourceLabel(row)}}</td>
        </tr>
      `).join("");
      const sourceTags = detail.sources.map((source) => {{
        if (source.source_url) {{
          return `<a class="tag source-link" href="${{source.source_url}}" target="_blank" rel="noopener noreferrer">${{source.source}}</a>`;
        }}
        return `<span class="tag">${{source.source}}</span>`;
      }});
      const rowSources = detail.pre_draft_history
        .filter((row) => row.source)
        .map((row) => row.source_url
          ? `<a class="tag source-link" href="${{row.source_url}}" target="_blank" rel="noopener noreferrer">${{row.source}}</a>`
          : `<span class="tag">${{row.source}}</span>`);
      document.getElementById("detail-sources").innerHTML = [...sourceTags, ...rowSources].join("");
    }}

    function renderStatEvidence(detail) {{
      const stats = detail.stat_evidence || {{}};
      const isGoalie = stats.role_group === "goalie";
      const section = document.getElementById("detail-stat-evidence-section");
      section.style.display = stats.stat_lines ? "block" : "none";
      if (!stats.stat_lines) return;
      const metrics = isGoalie ? [
        ["Goalie GP", stats.goalie_games || 0],
        ["SV%", decimalStat(stats.goalie_save_percentage, 3)],
        ["GAA", decimalStat(stats.goalie_goals_against_average, 2)],
        ["Record", `${{stats.goalie_wins || 0}}-${{stats.goalie_losses || 0}}`],
        ["SO", stats.goalie_shutouts || 0],
        ["Quality", decimalStat(stats.goalie_quality_score, 3)],
      ] : [
        ["GP", stats.games || 0],
        ["G-A-P", `${{stats.goals || 0}}-${{stats.assists || 0}}-${{stats.points || 0}}`],
        ["PPG", decimalStat(stats.points_per_game, 3)],
        ["Adult GP", stats.adult_games || 0],
        ["Playoff GP", stats.playoff_games || 0],
        ["Sources", stats.source_count || 0],
      ];
      document.getElementById("detail-stat-evidence").innerHTML = metrics.map(([label, value]) => `
        <div class="tool-grade">
          <div class="tool">${{label}}</div>
          <div class="grade">${{value}}</div>
        </div>
      `).join("");
      const tags = [
        `${{stats.stat_lines || 0}} stat rows`,
        `${{stats.league_count || 0}} leagues`,
        ...(stats.leagues || []).slice(0, 6),
      ];
      document.getElementById("detail-stat-evidence-tags").innerHTML =
        tags.map((label) => `<span class="tag">${{escapeHtml(String(label))}}</span>`).join("");
    }}

    function renderScouting(detail) {{
      const scouting = detail.scouting || {{}};
      const tools = scouting.tool_grades || [];
      const hasScouting = Boolean(scouting.summary || scouting.shades_of || (scouting.badges || []).length || tools.length);
      const section = document.getElementById("detail-scouting-section");
      section.style.display = hasScouting ? "block" : "none";
      if (!hasScouting) return;
      document.getElementById("detail-scouting-summary").textContent = scouting.summary || "Guide metadata captured; summary text unavailable.";
      const tags = [];
      if (scouting.shades_of) tags.push(`Shades of: ${{escapeHtml(scouting.shades_of)}}`);
      for (const badge of scouting.badges || []) tags.push(escapeHtml(badge));
      document.getElementById("detail-scouting-tags").innerHTML =
        tags.map((label) => `<span class="tag">${{label}}</span>`).join("");
      document.getElementById("detail-tool-grades").innerHTML = tools.map((item) => `
        <div class="tool-grade">
          <div class="tool">${{escapeHtml(String(item.tool || "").replaceAll("_", " "))}}</div>
          <div class="grade">${{Number(item.grade || 0).toFixed(1)}}</div>
        </div>
      `).join("");
    }}

    function renderTeamFit(detail) {{
      const options = detail.team_fit_options || [];
      const fallbackTeamFit = detail.team_fit || {{}};
      const section = document.getElementById("detail-team-fit-section");
      const hasTeamFit = Boolean(fallbackTeamFit.team_id || options.length);
      section.style.display = hasTeamFit ? "block" : "none";
      if (!hasTeamFit) return;
      const select = document.getElementById("detail-team-select");
      const defaultTeamId = selectedTeamByPlayer.get(detail.player_id) || fallbackTeamFit.team_id || detail.header.drafted_team_id || options[0]?.team_id || "";
      select.innerHTML = "";
      for (const optionFit of options) {{
        const option = document.createElement("option");
        option.value = optionFit.team_id;
        const draftedSuffix = optionFit.is_drafted_team ? " · drafted team" : "";
        option.textContent = `${{optionFit.team_name || optionFit.team_id}} (${{optionFit.team_id}})${{draftedSuffix}}`;
        select.appendChild(option);
      }}
      if (options.length) {{
        select.value = options.some((item) => item.team_id === defaultTeamId) ? defaultTeamId : options[0].team_id;
      }}
      select.onchange = () => {{
        selectedTeamByPlayer.set(detail.player_id, select.value);
        renderTeamFit(detail);
      }};
      select.style.display = options.length ? "block" : "none";
      const teamFit = options.find((item) => item.team_id === select.value) || fallbackTeamFit;
      document.getElementById("detail-team-fit-tags").innerHTML = [
        teamFit.team_id,
        teamFit.team_name,
        teamFit.need,
        teamFit.team_status_label,
        teamFit.ahl_coverage === "available" ? "AHL loaded" : "AHL missing",
        teamFit.role ? teamFit.role.replaceAll("_", " ") : "",
        `Fit ${{percent(teamFit.score || 0)}}`,
        `What-if ${{Number(teamFit.team_adjusted_score || fallbackTeamFit.team_adjusted_score || 0).toFixed(3)}}`,
        teamFit.is_drafted_team ? "Drafted team" : "What-if team",
      ].filter(Boolean).map((label) => `<span class="tag">${{escapeHtml(String(label))}}</span>`).join("");
      document.getElementById("detail-team-info").innerHTML = `
        <div><strong>${{escapeHtml(teamFit.team_name || teamFit.team_id || "Team")}}</strong> · ${{escapeHtml(teamFit.team_status_label || "Status pending")}}</div>
        <div>Role depth: ${{escapeHtml(teamFit.role || "").replaceAll("_", " ")}} · players ${{escapeHtml(teamFit.role_player_count ?? "—")}} / target ${{escapeHtml(teamFit.scarcity_target ?? "—")}} · U25 ${{escapeHtml(teamFit.u25_same_role_count ?? "—")}}</div>
        <div>${{escapeHtml(teamFit.roster_snapshot_label || "Roster snapshot pending")}} · ${{escapeHtml(teamFit.roster_snapshot_warning || "")}}</div>
      `;
      const components = [
        ["Roster", teamFit.roster_need_score],
        ["Pipeline", teamFit.pipeline_need_score],
        ["Timeline", teamFit.timeline_fit_score],
        ["Risk", teamFit.risk_appetite_score],
      ];
      document.getElementById("detail-team-fit-components").innerHTML = components.map(([label, value]) => `
        <div class="tool-grade">
          <div class="tool">${{escapeHtml(label)}}</div>
          <div class="grade">${{percent(value || 0)}}</div>
        </div>
      `).join("");
      document.getElementById("detail-team-fit-reason").textContent = teamFit.reason || "";
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
        ["Team Score", "team_adjusted_score"],
        ["Team Fit", "team_fit_score"],
        ["EP Tools", "ep_tool_score"],
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
          if (row && ["board_score", "team_adjusted_score", "team_fit_score", "ep_tool_score", "adjusted_production_score", "role_percentile", "average_league_weight"].includes(key)) {{
            value = Number(value).toFixed(3);
          }}
          if (row && ["adult_game_share", "playoff_game_share"].includes(key)) {{
            value = percent(value);
          }}
          html += `<div>${{value || "—"}}</div>`;
        }}
      }}
      html += "</div>";
      container.className = "";
      container.innerHTML = html;
    }}

    function exportShortlist() {{
      const rows = selectedExportRows();
      if (!rows.length) {{
        alert("Add players to the shortlist or compare set first.");
        return;
      }}
      const columns = ["player_id", "name", "board_rank", "consensus_rank", "board_score", "team_adjusted_score", "team_fit_need", "ep_tool_score", "short_reason", "risk_note"];
      const csv = [
        columns.join(","),
        ...rows.map((row) => columns.map((column) => `"${{String(row[column] ?? "").replaceAll('"', '""')}}"`).join(",")),
      ].join("\\n");
      downloadText(`draft-room-shortlist-${{payload.manifest.draft_year || "demo"}}.csv`, csv, "text/csv;charset=utf-8");
    }}

    function exportSummary() {{
      const rows = selectedExportRows();
      if (!rows.length) {{
        alert("Add players to the shortlist or compare set first.");
        return;
      }}
      const selectedLabel = shortlist.size ? "Shortlist" : "Compare Set";
      const date = new Date().toLocaleDateString(undefined, {{ year: "numeric", month: "short", day: "numeric" }});
      const highEvidenceCount = rows.filter((row) => row.evidence_depth === "high").length;
      const modelHigherCount = rows.filter((row) => row.disagreement_bucket === "model_higher").length;
      const consensusHigherCount = rows.filter((row) => row.disagreement_bucket === "consensus_higher").length;
      const playerCards = rows.map((row) => {{
        const detail = playerDetails[row.player_id];
        const story = storyForPlayer(row.player_id);
        const why = detail?.why_high || [];
        const risks = detail?.risk_flags || [];
        const sources = new Set((detail?.pre_draft_history || []).map((item) => item.source).filter(Boolean));
        const sourceText = [...sources].slice(0, 4).join(", ") || "source coverage pending";
        return `
          <section class="player">
            <div class="player-head">
              <div>
                <h2>${{escapeHtml(row.name)}}</h2>
                <p>${{escapeHtml(row.position)}} · ${{escapeHtml(row.primary_league)}} · ${{escapeHtml(row.primary_league_family)}}</p>
              </div>
              <div class="rank">Board ${{escapeHtml(row.board_rank)}}<span>Consensus ${{escapeHtml(row.consensus_rank)}}</span></div>
            </div>
            ${{story ? `<p class="story"><strong>${{escapeHtml(story.story_role)}}:</strong> ${{escapeHtml(story.story_hook)}}</p>` : ""}}
            <div class="metrics">
              <div><span>Evidence</span><strong>${{escapeHtml(evidenceLabel(row.evidence_depth))}}</strong></div>
              <div><span>Team</span><strong>${{Number(row.team_adjusted_score || row.board_score).toFixed(3)}}</strong></div>
              <div><span>EP Tools</span><strong>${{percent(row.ep_tool_score || 0)}}</strong></div>
              <div><span>Adjusted</span><strong>${{Number(row.adjusted_production_score).toFixed(3)}}</strong></div>
            </div>
            ${{row.team_fit_reason ? `<p class="story"><strong>${{escapeHtml(row.team_fit_need || "Team fit")}}:</strong> ${{escapeHtml(row.team_fit_reason)}}</p>` : ""}}
            <div class="columns">
              <div>
                <h3>Why Review</h3>
                <ul>${{why.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>
              </div>
              <div>
                <h3>Review Flags</h3>
                <ul>${{risks.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>
              </div>
            </div>
            <p class="sources">Sources: ${{escapeHtml(sourceText)}}</p>
          </section>
        `;
      }}).join("");
      const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Draft Room Summary ${{escapeHtml(payload.manifest.draft_year || "demo")}}</title>
  <style>
    body {{ margin: 0; padding: 32px; color: #0f172a; font-family: Inter, Arial, sans-serif; background: #f8fafc; }}
    .page {{ max-width: 980px; margin: 0 auto; }}
    header {{ border-bottom: 2px solid #0f172a; padding-bottom: 18px; margin-bottom: 20px; }}
    .eyebrow {{ color: #0f766e; font-size: 12px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }}
    h1 {{ margin: 6px 0 8px; font-size: 28px; }}
    p {{ margin: 0; color: #475569; line-height: 1.45; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 18px 0 24px; }}
    .summary div, .player {{ background: #fff; border: 1px solid #dbe2ea; border-radius: 8px; }}
    .summary div {{ padding: 12px; }}
    .summary span, .metrics span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 4px; }}
    .summary strong, .metrics strong {{ font-size: 18px; }}
    .player {{ padding: 18px; margin-bottom: 14px; break-inside: avoid; }}
    .player-head {{ display: flex; justify-content: space-between; gap: 18px; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 12px; }}
    h2 {{ margin: 0 0 4px; font-size: 20px; }}
    h3 {{ margin: 0 0 8px; font-size: 13px; text-transform: uppercase; color: #475569; }}
    .rank {{ text-align: right; font-weight: 800; font-size: 18px; }}
    .rank span {{ display: block; color: #64748b; font-size: 12px; font-weight: 600; margin-top: 4px; }}
    .story {{ background: #ccfbf1; color: #0f766e; padding: 10px 12px; border-radius: 8px; margin: 10px 0 12px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }}
    .metrics div {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }}
    .columns {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    ul {{ margin: 0; padding-left: 18px; color: #0f172a; line-height: 1.45; }}
    .sources {{ margin-top: 12px; font-size: 12px; }}
    @media print {{ body {{ background: #fff; padding: 0; }} .player {{ page-break-inside: avoid; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div class="eyebrow">Draft Room Intelligence</div>
      <h1>${{escapeHtml(payload.manifest.draft_year || "Demo")}} ${{escapeHtml(selectedLabel)}} Summary</h1>
      <p>Generated ${{escapeHtml(date)}} from a ${{escapeHtml(payload.manifest.dataset_status)}} demo package. This summary is a meeting artifact for review, not a final scouting grade.</p>
    </header>
    <section class="summary">
      <div><span>Players</span><strong>${{rows.length}}</strong></div>
      <div><span>High Evidence</span><strong>${{highEvidenceCount}}</strong></div>
      <div><span>Model Higher</span><strong>${{modelHigherCount}}</strong></div>
      <div><span>Consensus Higher</span><strong>${{consensusHigherCount}}</strong></div>
    </section>
    ${{playerCards}}
  </main>
</body>
</html>`;
      downloadText(`draft-room-summary-${{payload.manifest.draft_year || "demo"}}.html`, html, "text/html;charset=utf-8");
    }}

    function renderManifest() {{
      document.getElementById("stat-draft-year").textContent = payload.manifest.draft_year ?? "—";
      document.getElementById("stat-player-count").textContent = payload.manifest.player_count ?? 0;
      document.getElementById("stat-dataset-status").textContent = payload.manifest.dataset_status;
      document.getElementById("stat-featured-count").textContent = shortlist.size || demoStories.length || payload.manifest.featured_player_ids.length;
      const status = document.getElementById("status-badge");
      status.textContent = `Dataset: ${{payload.manifest.dataset_status}} · Shortlist: ${{shortlist.size}}`;
      status.className = `badge ${{payload.manifest.dataset_status === "strong" ? "badge-strong" : payload.manifest.dataset_status === "thin" ? "badge-thin" : ""}}`;
      const sources = document.getElementById("source-coverage");
      sources.innerHTML = Object.entries(payload.manifest.source_counts).map(([key, value]) => `<span class="tag">${{key}} · ${{value}}</span>`).join("");
      const featured = document.getElementById("featured-players");
      const storyById = Object.fromEntries(demoStories.map((story) => [story.player_id, story]));
      const featuredIds = demoStories.length ? demoStories.map((story) => story.player_id) : payload.manifest.featured_player_ids;
      featured.innerHTML = featuredIds.map((playerId) => {{
        const row = boardRows.find((item) => item.player_id === playerId);
        if (!row) return "";
        const story = storyById[playerId];
        return `
          <div class="featured-item">
            <div>
              ${{story ? `<div class="story-role">${{story.story_role}}</div>` : ""}}
              <div style="font-size:13px; font-weight:600;">${{row.name}}</div>
              <div style="font-size:12px; color:var(--muted);">Board ${{row.board_rank}} · Consensus ${{row.consensus_rank}} · ${{evidenceLabel(row.evidence_depth)}}</div>
              ${{story ? `<div class="story-hook">${{story.story_hook}}</div>` : `<div class="story-hook">Consensus delta ${{row.consensus_delta}}</div>`}}
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
      renderTeamView();
    }}

    function initializeTeamView() {{
      const select = document.getElementById("team-view-select");
      select.innerHTML = "";
      for (const team of teamViews) {{
        const option = document.createElement("option");
        option.value = team.team_id;
        option.textContent = `${{team.team_name}} (${{team.team_id}})`;
        select.appendChild(option);
      }}
      if (teamViews.length) select.value = selectedTeamViewId;
      select.addEventListener("change", () => {{
        selectedTeamViewId = select.value;
        renderTeamView();
      }});
    }}

    function renderTeamView() {{
      const summary = document.getElementById("team-view-summary");
      const gaps = document.getElementById("team-view-gaps");
      const matches = document.getElementById("team-view-matches");
      const select = document.getElementById("team-view-select");
      const team = teamViews.find((item) => item.team_id === selectedTeamViewId) || teamViews[0];
      if (!team) {{
        summary.textContent = "Team context is not available in this demo package.";
        gaps.innerHTML = "";
        matches.innerHTML = "";
        select.style.display = "none";
        return;
      }}
      select.style.display = "block";
      select.value = team.team_id;
      summary.innerHTML = `
        <div><strong>${{escapeHtml(team.team_name)}}</strong> · ${{escapeHtml(team.team_status_label || "")}}</div>
        <div>${{escapeHtml(team.snapshot_label || "")}} · ${{escapeHtml(team.ahl_coverage === "available" ? "AHL loaded" : "AHL missing")}}</div>
        <div>Strong matches ${{team.strong_match_count || 0}} · Useful matches ${{team.useful_match_count || 0}}</div>
      `;
      gaps.innerHTML = (team.role_gaps || []).slice(0, 4).map((gap) => `
        <div class="featured-item">
          <div>
            <div class="story-role">${{escapeHtml(String(gap.role_type || "").replaceAll("_", " "))}}</div>
            <div style="font-size:12px; color:var(--muted);">${{escapeHtml(gap.league_level)}} · players ${{gap.players}} / target ${{gap.scarcity_target}} · U25 ${{gap.under_25}}</div>
            <div class="story-hook">Scarcity ${{percent(gap.scarcity_score || 0)}} · priority ${{percent(gap.priority_score || 0)}}</div>
          </div>
        </div>
      `).join("");
      matches.innerHTML = (team.top_matches || []).slice(0, 5).map((match) => `
        <div class="featured-item">
          <div>
            <div style="font-size:13px; font-weight:600;">${{escapeHtml(match.name)}}</div>
            <div style="font-size:12px; color:var(--muted);">${{escapeHtml(match.position)}} · Board ${{match.board_rank}} · ${{escapeHtml(String(match.role || "").replaceAll("_", " "))}}</div>
            <div class="story-hook">${{escapeHtml(match.need)}} · fit ${{percent(match.score || 0)}} · pipeline ${{percent(match.pipeline_need_score || 0)}}</div>
          </div>
          <button class="small team-match-open" data-player-id="${{match.player_id}}">Open</button>
        </div>
      `).join("");
      matches.querySelectorAll(".team-match-open").forEach((button) => {{
        button.addEventListener("click", () => {{
          selectedPlayerId = button.dataset.playerId;
          selectedTeamByPlayer.set(selectedPlayerId, team.team_id);
          renderBoard();
          renderDetail();
        }});
      }});
    }}

    function loadDemoStories() {{
      const rows = storyRows();
      if (!rows.length) {{
        alert("No curated demo stories are present in this package.");
        return;
      }}
      shortlist.clear();
      for (const row of rows) {{
        shortlist.add(row.player_id);
      }}
      selectedPlayerId = rows[0].player_id;
      renderManifest();
      renderBoard();
      renderDetail();
    }}

    function loadDemoCompare() {{
      const rows = storyRows().slice(0, 3);
      if (!rows.length) {{
        alert("No curated demo stories are present in this package.");
        return;
      }}
      compare.splice(0, compare.length, ...rows.map((row) => row.player_id));
      selectedPlayerId = rows[0].player_id;
      renderCompare();
      renderBoard();
      renderDetail();
    }}

    function bindEvents() {{
      for (const id of ["filter-position", "filter-league-family", "filter-competition", "filter-disagreement", "filter-evidence", "filter-search"]) {{
        document.getElementById(id).addEventListener("input", renderBoard);
      }}
      document.getElementById("export-shortlist").addEventListener("click", exportShortlist);
      document.getElementById("export-summary").addEventListener("click", exportSummary);
      document.getElementById("load-demo-stories").addEventListener("click", loadDemoStories);
      document.getElementById("load-demo-compare").addEventListener("click", loadDemoCompare);
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
    initializeTeamView();
    renderManifest();
    bindEvents();
    renderBoard();
    renderDetail();
    renderCompare();
  </script>
</body>
</html>
"""
