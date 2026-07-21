"""Generate a deterministic one-page meeting brief for the guided demo stories."""

# ruff: noqa: E501

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from draft_room_intelligence.reports.demo_export import DemoExportBundle


@dataclass(frozen=True)
class DemoBriefOutputs:
    html_path: Path
    pdf_path: Path
    player_count: int


def write_demo_meeting_brief(
    output_dir: str | Path,
    bundle: DemoExportBundle,
    *,
    player_limit: int = 6,
) -> DemoBriefOutputs:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    stories = select_story_rows(bundle, player_limit=player_limit)
    html_path = root / "meeting_brief.html"
    pdf_path = root / "meeting_brief.pdf"
    html_path.write_text(render_brief_html(bundle, stories), encoding="utf-8")
    write_brief_pdf(pdf_path, bundle, stories)
    return DemoBriefOutputs(html_path=html_path, pdf_path=pdf_path, player_count=len(stories))


def select_story_rows(bundle: DemoExportBundle, *, player_limit: int) -> list[dict[str, object]]:
    board_by_id = {row["player_id"]: row for row in bundle.board_rows}
    details_by_id = {detail["player_id"]: detail for detail in bundle.player_details}
    selected: list[dict[str, object]] = []
    for story in bundle.manifest.get("demo_story_players", [])[:player_limit]:
        player_id = story.get("player_id", "")
        row = board_by_id.get(player_id)
        if not row:
            continue
        selected.append(
            {
                "story": story,
                "board": row,
                "detail": details_by_id.get(player_id, {}),
            }
        )
    return selected


def render_brief_html(bundle: DemoExportBundle, stories: list[dict[str, object]]) -> str:
    draft_year = html.escape(str(bundle.manifest.get("draft_year", "Demo")))
    status = html.escape(str(bundle.manifest.get("dataset_status", "unknown")))
    cards = "".join(render_html_card(item) for item in stories)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{draft_year} Draft Meeting Brief</title>
  <style>
    @page {{ size: A4 landscape; margin: 9mm; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: #0f172a; font-family: Arial, sans-serif; background: #fff; }}
    header {{ display: flex; justify-content: space-between; align-items: end; border-bottom: 2px solid #0f766e; padding-bottom: 7px; margin-bottom: 8px; }}
    h1 {{ margin: 0; font-size: 20px; }}
    header p {{ margin: 3px 0 0; color: #475569; font-size: 9px; }}
    .status {{ font-size: 10px; font-weight: 700; color: #0f766e; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-template-rows: repeat(3, 1fr); gap: 7px; height: 170mm; }}
    article {{ border: 1px solid #cbd5e1; padding: 8px; overflow: hidden; }}
    .head {{ display: flex; justify-content: space-between; gap: 8px; }}
    h2 {{ margin: 0; font-size: 13px; }}
    .meta, .source {{ color: #64748b; font-size: 8px; margin-top: 2px; }}
    .rank {{ text-align: right; font-size: 10px; font-weight: 700; white-space: nowrap; }}
    .rank span {{ display: block; color: #64748b; font-size: 8px; font-weight: 400; }}
    .story {{ margin: 6px 0; padding: 5px 6px; background: #ecfdf5; color: #115e59; font-size: 8.5px; line-height: 1.3; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 5px; }}
    .metrics div {{ background: #f8fafc; padding: 4px; font-size: 7px; color: #64748b; }}
    .metrics strong {{ display: block; color: #0f172a; font-size: 9px; margin-top: 1px; }}
    .line {{ font-size: 8px; line-height: 1.35; margin: 3px 0; }}
    .label {{ color: #64748b; font-weight: 700; text-transform: uppercase; font-size: 7px; }}
    footer {{ margin-top: 6px; color: #64748b; font-size: 7px; }}
  </style>
</head>
<body>
  <header>
    <div><h1>{draft_year} Guided Draft Meeting Brief</h1><p>Six discussion anchors from the current demo board. Review aid, not a final scouting grade.</p></div>
    <div class="status">Dataset: {status} &middot; {len(bundle.board_rows)} players</div>
  </header>
  <main class="grid">{cards}</main>
  <footer>Board score blends model, consensus, and scouting evidence. Team-adjusted score adds organization context. Source and coverage caveats remain visible in the full demo.</footer>
</body>
</html>
"""


def render_html_card(item: dict[str, object]) -> str:
    story = item["story"]
    row = item["board"]
    detail = item["detail"]
    evidence = detail.get("stat_evidence", {})
    risks = detail.get("risk_flags", [])
    team_fit = detail.get("team_fit", {})
    source_names = sorted(
        {
            str(history.get("source", ""))
            for history in detail.get("pre_draft_history", [])
            if history.get("source")
        }
    )
    return f"""<article>
      <div class="head"><div><h2>{escape(row.get('name'))}</h2><div class="meta">{escape(row.get('position'))} &middot; {escape(row.get('primary_league'))} &middot; {escape(row.get('primary_league_family'))}</div></div><div class="rank">Board {escape(row.get('board_rank'))}<span>Consensus {escape(row.get('consensus_rank'))}</span></div></div>
      <div class="story"><strong>{escape(story.get('story_role'))}:</strong> {escape(story.get('story_hook'))}</div>
      <div class="metrics"><div>Evidence<strong>{escape(row.get('evidence_depth'))}</strong></div><div>Board<strong>{decimal(row.get('board_score'))}</strong></div><div>Team<strong>{decimal(row.get('team_adjusted_score'))}</strong></div><div>GP<strong>{escape(evidence.get('games'))}</strong></div></div>
      <div class="line"><span class="label">Stat signal</span> {escape(stat_signal(evidence))}</div>
      <div class="line"><span class="label">Team context</span> {escape(team_fit.get('need') or row.get('team_fit_need'))} for {escape(team_fit.get('team_name') or row.get('team_fit_team'))}; fit {percent(team_fit.get('score') or row.get('team_fit_score'))}.</div>
      <div class="line"><span class="label">Review flag</span> {escape(risks[0] if risks else 'No major coverage flag in the current dataset.')}</div>
      <div class="source">Sources: {escape(', '.join(source_names[:4]) or 'coverage pending')}</div>
    </article>"""


def write_brief_pdf(path: Path, bundle: DemoExportBundle, stories: list[dict[str, object]]) -> None:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height))
    margin = 26
    pdf.setTitle(f"{bundle.manifest.get('draft_year', 'Demo')} Draft Meeting Brief")
    pdf.setFillColorRGB(0.06, 0.09, 0.16)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(margin, page_height - 30, f"{bundle.manifest.get('draft_year', 'Demo')} Guided Draft Meeting Brief")
    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColorRGB(0.28, 0.35, 0.43)
    pdf.drawString(margin, page_height - 43, "Six discussion anchors from the current demo board. Review aid, not a final scouting grade.")
    pdf.setStrokeColorRGB(0.06, 0.46, 0.43)
    pdf.setLineWidth(1.5)
    pdf.line(margin, page_height - 50, page_width - margin, page_height - 50)

    gap = 8
    card_width = (page_width - (margin * 2) - gap) / 2
    card_height = 164
    top = page_height - 60
    for index, item in enumerate(stories[:6]):
        column = index % 2
        row_index = index // 2
        x = margin + column * (card_width + gap)
        y = top - (row_index + 1) * card_height - row_index * gap
        draw_pdf_card(pdf, item, x, y, card_width, card_height, stringWidth)

    pdf.setFillColorRGB(0.28, 0.35, 0.43)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(margin, 12, "Board score blends model, consensus, and scouting evidence. Team-adjusted score adds organization context.")
    pdf.showPage()
    pdf.save()


def draw_pdf_card(pdf, item, x, y, width, height, string_width) -> None:
    story = item["story"]
    row = item["board"]
    detail = item["detail"]
    evidence = detail.get("stat_evidence", {})
    risks = detail.get("risk_flags", [])
    team_fit = detail.get("team_fit", {})
    pdf.setStrokeColorRGB(0.80, 0.84, 0.88)
    pdf.setLineWidth(0.6)
    pdf.rect(x, y, width, height, stroke=1, fill=0)
    cursor = y + height - 15
    pdf.setFillColorRGB(0.06, 0.09, 0.16)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 8, cursor, str(row.get("name", "")))
    pdf.setFont("Helvetica-Bold", 8)
    rank = f"Board {row.get('board_rank', '')} / Consensus {row.get('consensus_rank', '')}"
    pdf.drawRightString(x + width - 8, cursor, rank)
    cursor -= 12
    pdf.setFont("Helvetica", 7)
    pdf.setFillColorRGB(0.28, 0.35, 0.43)
    pdf.drawString(x + 8, cursor, f"{row.get('position', '')} | {row.get('primary_league', '')} | evidence {row.get('evidence_depth', '')}")
    cursor -= 15
    pdf.setFillColorRGB(0.06, 0.37, 0.35)
    pdf.setFont("Helvetica-Bold", 7.5)
    cursor = draw_wrapped_text(
        pdf,
        f"{story.get('story_role', '')}: {story.get('story_hook', '')}",
        x + 8,
        cursor,
        width - 16,
        7.5,
        9,
        string_width,
        font_name="Helvetica-Bold",
        max_lines=2,
    )
    cursor -= 3
    pdf.setFillColorRGB(0.06, 0.09, 0.16)
    pdf.setFont("Helvetica", 7)
    lines = [
        f"Scores: board {decimal(row.get('board_score'))} | team {decimal(row.get('team_adjusted_score'))} | GP {evidence.get('games', '')}",
        f"Stat: {stat_signal(evidence)}",
        f"Team: {team_fit.get('need') or row.get('team_fit_need', '')} for {team_fit.get('team_name') or row.get('team_fit_team', '')}; fit {percent(team_fit.get('score') or row.get('team_fit_score'))}",
        f"Flag: {risks[0] if risks else 'No major coverage flag in the current dataset.'}",
    ]
    for text in lines:
        cursor = draw_wrapped_text(
            pdf,
            text,
            x + 8,
            cursor,
            width - 16,
            7,
            8.5,
            string_width,
            font_name="Helvetica",
            max_lines=2,
        )
        cursor -= 2


def draw_wrapped_text(
    pdf,
    text,
    x,
    y,
    width,
    font_size,
    leading,
    string_width,
    *,
    font_name,
    max_lines,
):
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if string_width(candidate, font_name, font_size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    for line in lines[:max_lines]:
        pdf.drawString(x, y, line)
        y -= leading
    return y


def stat_signal(evidence: dict[str, object]) -> str:
    if evidence.get("role_group") == "goalie":
        return (
            f"{number(evidence.get('goalie_save_percentage')):.3f} SV%, "
            f"{number(evidence.get('goalie_goals_against_average')):.2f} GAA, "
            f"{evidence.get('goalie_wins', 0)}-{evidence.get('goalie_losses', 0)}, "
            f"{evidence.get('goalie_shutouts', 0)} SO"
        )
    return (
        f"{evidence.get('goals', 0)}-{evidence.get('assists', 0)}-"
        f"{evidence.get('points', 0)}, {number(evidence.get('points_per_game')):.2f} PPG"
    )


def escape(value: object) -> str:
    return html.escape(str(value or ""))


def decimal(value: object) -> str:
    return f"{number(value):.3f}"


def percent(value: object) -> str:
    return f"{number(value):.0%}"


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
