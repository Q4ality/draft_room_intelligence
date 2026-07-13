"""Import local Elite Prospects draft-guide PDFs into normalized tables."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Protocol
from urllib.request import Request
from urllib.request import urlopen

from draft_room_intelligence.data.eliteprospects_csv import (
    PLAYER_COLUMNS,
    SEASON_STAT_LINE_COLUMNS,
    build_player_id,
    write_table,
)
from draft_room_intelligence.data.league_standardization import normalize_league_name


EP_PDF_PROFILE_COLUMNS = [
    "player_id",
    "draft_year",
    "name",
    "page_start",
    "page_end",
    "rank",
    "rank_range",
    "grade",
    "position",
    "handedness",
    "height_text",
    "height_cm",
    "weight_kg",
    "birth_date",
    "shades_of",
    "badges",
    "profile_summary",
    "profile_text_chars",
    "extraction_warnings",
    "source",
    "source_id",
    "source_url",
]

EP_PDF_TOOL_GRADE_COLUMNS = [
    "player_id",
    "tool",
    "grade",
    "source",
    "source_id",
    "source_url",
]

EP_PDF_INDEX_COLUMNS = [
    "player_id",
    "draft_year",
    "rank",
    "name",
    "position",
    "team",
    "league",
    "grade",
    "profile_page",
    "source",
    "source_id",
    "source_url",
]

EP_PDF_VISION_USAGE_COLUMNS = [
    "player_id",
    "name",
    "page",
    "model",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "source",
    "source_id",
    "source_url",
]

RANKING_COLUMNS = [
    "player_id",
    "draft_year",
    "source",
    "rank",
    "scope",
    "position",
    "source_id",
    "source_url",
]

SKATER_TOOL_LABELS = ["skating", "shooting", "passing", "handling", "sense", "physical"]
GOALIE_TOOL_LABELS = [
    "skating",
    "athleticism",
    "transitions",
    "positioning",
    "play_reading",
    "technique",
]
GOALIE_TOOL_LABELS_2025 = [
    "skating",
    "transitions",
    "hands",
    "tracking",
    "post",
    "depth",
]
GOALIE_TOOL_LABELS_2026 = GOALIE_TOOL_LABELS
TOOL_LABELS = SKATER_TOOL_LABELS
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_VISION_MODEL = "gpt-5.6"


class ToolGradeVisionClient(Protocol):
    def extract_tool_grades(
        self,
        image_path: Path,
        profile: EliteProspectsPdfProfile,
    ) -> dict[str, str]:
        """Return tool grades keyed by skating/shooting/passing/handling/sense/physical."""


@dataclass(frozen=True)
class EliteProspectsPdfProfile:
    player_id: str
    draft_year: int
    name: str
    page_start: int
    page_end: int
    rank: str
    rank_range: str
    grade: str
    position: str
    handedness: str
    height_text: str
    height_cm: str
    weight_kg: str
    birth_date: str
    shades_of: str
    badges: tuple[str, ...]
    profile_summary: str
    profile_text: str
    stat_lines: tuple[dict[str, str], ...]
    tool_grades: tuple[dict[str, str], ...]
    extraction_warnings: tuple[str, ...]
    source_url: str


@dataclass(frozen=True)
class EliteProspectsPdfExport:
    players: list[dict[str, str]]
    season_stat_lines: list[dict[str, str]]
    rankings: list[dict[str, str]]
    profiles: list[EliteProspectsPdfProfile]
    profile_rows: list[dict[str, str]]
    tool_grade_rows: list[dict[str, str]]
    index_rows: list[dict[str, str]]
    vision_usage_rows: list[dict[str, str]]


def write_eliteprospects_pdf_tables(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    draft_year: int,
    page_start: int = 1,
    page_end: int | None = None,
    profile_limit: int | None = None,
    index_page_start: int | None = None,
    index_page_end: int | None = None,
    vision_missing_tool_grades: bool = False,
    vision_model: str = DEFAULT_VISION_MODEL,
    vision_api_key: str | None = None,
    pdftoppm_path: str | Path = "pdftoppm",
    vision_render_dpi: int = 160,
    vision_client: ToolGradeVisionClient | None = None,
) -> EliteProspectsPdfExport:
    pdf_path = Path(pdf_path)
    source_name = pdf_path.name
    if index_page_start is None and page_start > 5:
        index_page_start = 5
    if index_page_end is None and index_page_start is not None:
        index_page_end = page_start - 1
    index_rows: list[dict[str, str]] = []
    if index_page_start is not None and index_page_end is not None and index_page_end >= index_page_start:
        index_page_texts = extract_pdf_page_texts(
            pdf_path,
            page_start=index_page_start,
            page_end=index_page_end,
        )
        index_rows = parse_player_index_rows(
            index_page_texts,
            draft_year=draft_year,
            source_name=source_name,
        )
    page_texts = extract_pdf_page_texts(pdf_path, page_start=page_start, page_end=page_end)
    export = normalize_eliteprospects_pdf_pages(
        page_texts,
        draft_year=draft_year,
        source_name=source_name,
        profile_limit=profile_limit,
        index_rows=index_rows,
    )
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    if vision_missing_tool_grades:
        export = enrich_missing_tool_grades_with_vision(
            Path(pdf_path),
            root / "vision_pages",
            export,
            model=vision_model,
            api_key=vision_api_key,
            pdftoppm_path=pdftoppm_path,
            render_dpi=vision_render_dpi,
            vision_client=vision_client,
        )
    write_table(root / "players.csv", PLAYER_COLUMNS, export.players)
    write_table(root / "season_stat_lines.csv", SEASON_STAT_LINE_COLUMNS, export.season_stat_lines)
    write_table(root / "rankings.csv", RANKING_COLUMNS, export.rankings)
    write_table(root / "ep_pdf_profiles.csv", EP_PDF_PROFILE_COLUMNS, export.profile_rows)
    write_table(root / "ep_pdf_tool_grades.csv", EP_PDF_TOOL_GRADE_COLUMNS, export.tool_grade_rows)
    write_table(root / "ep_pdf_player_index.csv", EP_PDF_INDEX_COLUMNS, export.index_rows)
    write_table(root / "ep_pdf_vision_usage.csv", EP_PDF_VISION_USAGE_COLUMNS, export.vision_usage_rows)
    report = format_pdf_extraction_report(export)
    (root / "extraction_report.md").write_text(report, encoding="utf-8")
    return export


def enrich_missing_tool_grades_with_vision(
    pdf_path: Path,
    image_dir: Path,
    export: EliteProspectsPdfExport,
    *,
    model: str = DEFAULT_VISION_MODEL,
    api_key: str | None = None,
    pdftoppm_path: str | Path = "pdftoppm",
    render_dpi: int = 160,
    vision_client: ToolGradeVisionClient | None = None,
) -> EliteProspectsPdfExport:
    client = vision_client or OpenAiVisionToolGradeClient(
        model=model,
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
    )
    profiles: list[EliteProspectsPdfProfile] = []
    vision_usage_rows = list(export.vision_usage_rows)
    for profile in export.profiles:
        if profile.tool_grades or "missing_tool_grades" not in profile.extraction_warnings:
            profiles.append(profile)
            continue
        image_path = render_pdf_page(
            pdf_path,
            image_dir,
            page_number=profile.page_start,
            pdftoppm_path=pdftoppm_path,
            dpi=render_dpi,
        )
        tool_labels = tool_labels_for_profile(profile)
        grades = normalize_tool_grade_map(
            client.extract_tool_grades(image_path, profile),
            allowed_tools=tool_labels,
        )
        usage = getattr(client, "last_usage", None)
        if isinstance(usage, dict):
            vision_usage_rows.append(
                vision_usage_row(
                    profile,
                    model=getattr(client, "model", model),
                    usage=usage,
                )
            )
        if grades:
            source_id = f"{profile.draft_year}-ep-pdf-page-{profile.page_start}"
            tool_grades = tuple(
                {
                    "player_id": profile.player_id,
                    "tool": tool,
                    "grade": grades[tool],
                    "source": "eliteprospects_pdf_vision",
                    "source_id": source_id,
                    "source_url": profile.source_url,
                }
                for tool in tool_labels
                if tool in grades
            )
            warnings = tuple(
                warning
                for warning in profile.extraction_warnings
                if warning != "missing_tool_grades"
            )
            profiles.append(
                replace(
                    profile,
                    tool_grades=tool_grades,
                    extraction_warnings=(*warnings, "tool_grades_from_vision"),
                )
            )
        else:
            profiles.append(profile)
    return build_export_from_profiles(
        profiles,
        index_rows=export.index_rows,
        vision_usage_rows=vision_usage_rows,
    )


class OpenAiVisionToolGradeClient:
    def __init__(
        self,
        *,
        model: str = DEFAULT_VISION_MODEL,
        api_key: str,
        endpoint: str = OPENAI_RESPONSES_URL,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for --vision-missing-tool-grades")
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint
        self.last_usage: dict[str, str] = {}

    def extract_tool_grades(
        self,
        image_path: Path,
        profile: EliteProspectsPdfProfile,
    ) -> dict[str, str]:
        base64_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        image_url = f"data:image/png;base64,{base64_image}"
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": tool_grade_prompt(profile),
                        },
                        {
                            "type": "input_image",
                            "image_url": image_url,
                        },
                    ],
                }
            ],
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        self.last_usage = normalize_vision_usage(response_payload.get("usage"))
        return parse_tool_grade_json(
            extract_response_text(response_payload),
            allowed_tools=tool_labels_for_profile(profile),
        )


def tool_grade_prompt(profile: EliteProspectsPdfProfile) -> str:
    labels = tool_labels_for_profile(profile)
    if is_goalie_profile(profile):
        visible_labels = (
            "SKATING, TRANSITIONS, HANDS, TRACKING, POST, DEPTH"
            if profile.draft_year == 2025
            else "SKATING, ATHLETICISM, TRANSITIONS, POSITIONING, PLAY READING, TECHNIQUE"
        )
        role_lines = [
            "This is a goalie profile. Extract goalie tool grades only.",
            f"The visible goalie labels should be: {visible_labels}.",
            "Map PLAY READING to the JSON key play_reading.",
        ]
    else:
        role_lines = ["This is a skater profile. Extract skater tool grades only."]
    return "\n".join(
        [
            "Extract only the six Elite Prospects tool grade numbers visible on this player profile.",
            *role_lines,
            f"Player: {profile.name}",
            "Return strict JSON with exactly these lowercase keys when visible:",
            ", ".join(labels) + ".",
            "Values must be strings like \"6.5\" or \"8.0\".",
            "Do not infer hidden values. If a value is not visible, omit that key.",
            "Return JSON only.",
        ]
    )


def tool_labels_for_profile(profile: EliteProspectsPdfProfile) -> list[str]:
    if not is_goalie_profile(profile):
        return SKATER_TOOL_LABELS
    if profile.draft_year == 2025:
        return GOALIE_TOOL_LABELS_2025
    return GOALIE_TOOL_LABELS_2026


def is_goalie_profile(profile: EliteProspectsPdfProfile) -> bool:
    return profile.position == "G"


def render_pdf_page(
    pdf_path: Path,
    image_dir: Path,
    *,
    page_number: int,
    pdftoppm_path: str | Path = "pdftoppm",
    dpi: int = 160,
) -> Path:
    image_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = image_dir / f"page_{page_number}"
    subprocess.run(
        [
            str(pdftoppm_path),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-png",
            "-singlefile",
            "-r",
            str(dpi),
            str(pdf_path),
            str(output_prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    image_path = output_prefix.with_suffix(".png")
    if not image_path.exists():
        raise RuntimeError(f"pdftoppm did not create expected image: {image_path}")
    return image_path


def extract_response_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    parts: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts)


def parse_tool_grade_json(
    text: str,
    *,
    allowed_tools: list[str] | None = None,
) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI vision response was not valid JSON: {text[:200]}") from exc
    if not isinstance(payload, dict):
        raise ValueError("OpenAI vision response must be a JSON object")
    return normalize_tool_grade_map(payload, allowed_tools=allowed_tools)


def normalize_tool_grade_map(
    values: dict,
    *,
    allowed_tools: list[str] | None = None,
) -> dict[str, str]:
    grades: dict[str, str] = {}
    allowed = set(allowed_tools or SKATER_TOOL_LABELS)
    for raw_tool, raw_grade in values.items():
        tool = str(raw_tool).strip().lower().replace(" ", "_")
        if tool not in allowed or raw_grade in ("", None):
            continue
        grade = normalize_tool_grade_value(str(raw_grade))
        if grade:
            grades[tool] = grade
    return grades


def normalize_vision_usage(usage: object) -> dict[str, str]:
    if not isinstance(usage, dict):
        return {}
    return {
        "input_tokens": str(usage.get("input_tokens", "") or ""),
        "output_tokens": str(usage.get("output_tokens", "") or ""),
        "total_tokens": str(usage.get("total_tokens", "") or ""),
    }


def vision_usage_row(
    profile: EliteProspectsPdfProfile,
    *,
    model: str,
    usage: dict[str, str],
) -> dict[str, str]:
    source_id = f"{profile.draft_year}-ep-pdf-page-{profile.page_start}"
    return {
        "player_id": profile.player_id,
        "name": profile.name,
        "page": str(profile.page_start),
        "model": model,
        "input_tokens": usage.get("input_tokens", ""),
        "output_tokens": usage.get("output_tokens", ""),
        "total_tokens": usage.get("total_tokens", ""),
        "source": "eliteprospects_pdf_vision",
        "source_id": source_id,
        "source_url": profile.source_url,
    }


def normalize_tool_grade_value(value: str) -> str:
    match = re.search(r"([1-9](?:\.\d)?)", value)
    if not match:
        return ""
    grade = float(match.group(1))
    if grade < 1 or grade > 9:
        return ""
    return f"{grade:.1f}"


def extract_pdf_page_texts(
    pdf_path: str | Path,
    *,
    page_start: int = 1,
    page_end: int | None = None,
) -> list[tuple[int, str]]:
    try:
        import pypdf
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for Elite Prospects PDF import. "
            "Install project dependencies with `make install-dev`."
        ) from exc

    reader = pypdf.PdfReader(str(pdf_path))
    final_page = page_end or len(reader.pages)
    page_texts: list[tuple[int, str]] = []
    for page_number in range(max(1, page_start), min(final_page, len(reader.pages)) + 1):
        page = reader.pages[page_number - 1]
        page_texts.append((page_number, page.extract_text() or ""))
    return page_texts


def normalize_eliteprospects_pdf_pages(
    page_texts: list[tuple[int, str]],
    *,
    draft_year: int,
    source_name: str = "eliteprospects_pdf",
    profile_limit: int | None = None,
    index_rows: list[dict[str, str]] | None = None,
) -> EliteProspectsPdfExport:
    profiles: list[EliteProspectsPdfProfile] = []
    index_rows_by_page = {row["profile_page"]: row for row in index_rows or []}
    for page_number, text in page_texts:
        profile = parse_profile_page(
            text,
            draft_year=draft_year,
            page_number=page_number,
            source_name=source_name,
            index_row=index_rows_by_page.get(str(page_number)),
        )
        if profile is None:
            continue
        profiles.append(profile)
        if profile_limit is not None and len(profiles) >= profile_limit:
            break

    return build_export_from_profiles(profiles, index_rows=index_rows or [])


def build_export_from_profiles(
    profiles: list[EliteProspectsPdfProfile],
    *,
    index_rows: list[dict[str, str]] | None = None,
    vision_usage_rows: list[dict[str, str]] | None = None,
) -> EliteProspectsPdfExport:
    players = [profile_to_player_row(profile) for profile in profiles]
    stat_lines = [line for profile in profiles for line in profile.stat_lines]
    rankings = [profile_to_ranking_row(profile) for profile in profiles if profile.rank]
    profile_rows = [profile_to_profile_row(profile) for profile in profiles]
    tool_grade_rows = [row for profile in profiles for row in profile.tool_grades]
    return EliteProspectsPdfExport(
        players=players,
        season_stat_lines=stat_lines,
        rankings=rankings,
        profiles=profiles,
        profile_rows=profile_rows,
        tool_grade_rows=tool_grade_rows,
        index_rows=index_rows or [],
        vision_usage_rows=vision_usage_rows or [],
    )


def parse_player_index_rows(
    page_texts: list[tuple[int, str]],
    *,
    draft_year: int,
    source_name: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_pages: set[str] = set()
    pattern = re.compile(
        r"^(?P<rank>\d{1,3})\s+"
        r"(?P<name>.+?),\s+"
        r"(?P<position>[A-Z]{1,3}(?:/[A-Z]{1,3})?)\s+"
        r"(?P<team>.+?)\s+"
        r"(?P<grade>[ABCDF])\s+Grade\s+"
        r"(?P<profile_page>\d{1,4})$"
    )
    for index_page, text in page_texts:
        for raw_line in text.splitlines():
            line = clean_text(raw_line)
            match = pattern.match(line)
            if not match:
                continue
            profile_page = match.group("profile_page")
            if profile_page in seen_pages:
                continue
            name = clean_text(match.group("name"))
            team, league = split_team_league(match.group("team"))
            source_id = f"{draft_year}-ep-pdf-index-page-{index_page}"
            rows.append(
                {
                    "player_id": build_player_id(draft_year, "", name),
                    "draft_year": str(draft_year),
                    "rank": match.group("rank"),
                    "name": name,
                    "position": normalize_pdf_position(match.group("position")),
                    "team": team or clean_text(match.group("team")),
                    "league": normalize_league_name(league) if league else "",
                    "grade": match.group("grade"),
                    "profile_page": profile_page,
                    "source": "eliteprospects_pdf_index",
                    "source_id": source_id,
                    "source_url": f"{source_name}#page={index_page}",
                }
            )
            seen_pages.add(profile_page)
    return rows


def apply_index_rows(
    export: EliteProspectsPdfExport,
    index_rows: list[dict[str, str]],
) -> EliteProspectsPdfExport:
    if not index_rows:
        return build_export_from_profiles(
            export.profiles,
            index_rows=[],
            vision_usage_rows=export.vision_usage_rows,
        )
    rows_by_page = {row["profile_page"]: row for row in index_rows}
    profiles: list[EliteProspectsPdfProfile] = []
    for profile in export.profiles:
        index_row = rows_by_page.get(str(profile.page_start))
        if not index_row:
            profiles.append(profile)
            continue
        profiles.append(
            replace(
                profile,
                rank=profile.rank or index_row["rank"],
                grade=profile.grade or index_row["grade"],
                position=profile.position or index_row["position"],
            )
        )
    return build_export_from_profiles(
        profiles,
        index_rows=index_rows,
        vision_usage_rows=export.vision_usage_rows,
    )


def parse_profile_page(
    text: str,
    *,
    draft_year: int,
    page_number: int,
    source_name: str,
    index_row: dict[str, str] | None = None,
) -> EliteProspectsPdfProfile | None:
    if not looks_like_profile_page(text):
        return None

    warnings: list[str] = []
    name, position_hint = extract_name_and_position(text)
    if not name and index_row:
        name = index_row["name"]
        position_hint = index_row["position"]
    if not name:
        return None
    source_id = f"{draft_year}-ep-pdf-page-{page_number}"
    player_id = build_player_id(draft_year, "", name)
    source_url = f"{source_name}#page={page_number}"

    bio = extract_bio(text, position_hint=position_hint)
    position = bio.get("position", "") or (index_row["position"] if index_row else "")
    for key in ("birth_date", "height_cm", "weight_kg"):
        if not bio.get(key):
            warnings.append(f"missing_{key}")
    if not position:
        warnings.append("missing_position")

    rank_range = extract_rank_range(text)
    rank = (index_row["rank"] if index_row else "") or extract_rank(text, rank_range=rank_range)
    grade = (index_row["grade"] if index_row else "") or extract_grade(text)
    stat_lines = tuple(
        build_stat_line(
            player_id,
            row,
            source_id=source_id,
            source_url=source_url,
        )
        for row in extract_stat_rows(text, draft_year=draft_year)
    )
    if not stat_lines:
        warnings.append("missing_stat_lines")

    tool_grades = tuple(
        {
            "player_id": player_id,
            "tool": tool,
            "grade": grade_value,
            "source": "eliteprospects_pdf",
            "source_id": source_id,
            "source_url": source_url,
        }
        for tool, grade_value in extract_tool_grades(text).items()
    )
    if not tool_grades:
        warnings.append("missing_tool_grades")

    return EliteProspectsPdfProfile(
        player_id=player_id,
        draft_year=draft_year,
        name=name,
        page_start=page_number,
        page_end=page_number,
        rank=rank,
        rank_range=rank_range,
        grade=grade,
        position=position,
        handedness=bio.get("handedness", ""),
        height_text=bio.get("height_text", ""),
        height_cm=bio.get("height_cm", ""),
        weight_kg=bio.get("weight_kg", ""),
        birth_date=bio.get("birth_date", ""),
        shades_of=extract_shades_of(text),
        badges=tuple(extract_badges(text, grade=grade)),
        profile_summary=extract_profile_summary(text),
        profile_text=extract_profile_text(text, name=name),
        stat_lines=stat_lines,
        tool_grades=tool_grades,
        extraction_warnings=tuple(warnings),
        source_url=source_url,
    )


def looks_like_profile_page(text: str) -> bool:
    normalized = text.upper()
    return (
        ("STATISTICS" in normalized or "TEAM LEAGUE GP" in normalized)
        and ("POSITION(S)" in normalized or "TOOL GRADES" in normalized)
        and "PLAYER INDEX" not in normalized
        and "GRADE PROSPECTS" not in normalized
    )


def extract_name_and_position(text: str) -> tuple[str, str]:
    pipe_match = re.search(r"\n(?P<position>[A-Z][A-Z/]{0,5})\|(?P<name>[^\n]+)", text)
    if pipe_match:
        return clean_text(pipe_match.group("name")), pipe_match.group("position")

    shades_match = re.search(r"^\s*(?P<name>.+?)\s+SHADES OF\.\.\.", text, flags=re.IGNORECASE)
    if shades_match:
        return clean_text(shades_match.group("name")), ""
    return "", ""


def extract_bio(text: str, *, position_hint: str) -> dict[str, str]:
    bio: dict[str, str] = {}
    compact = clean_text(text)
    match_2025 = re.search(
        r"(?P<weight>\d{3})\s*lbs\s+(?P<handedness>[LR])(?P<height>\d+[\'’][0-9.]+[\"”])\s+"
        r"(?P<birth_date>\d{4}-\d{2}-\d{2})",
        compact,
    )
    if match_2025:
        bio.update(
            {
                "position": normalize_pdf_position(position_hint),
                "handedness": match_2025.group("handedness"),
                "height_text": match_2025.group("height"),
                "height_cm": str(height_to_cm(match_2025.group("height"))),
                "weight_kg": str(pounds_to_kg(match_2025.group("weight"))),
                "birth_date": match_2025.group("birth_date"),
            }
        )
        return bio

    match_2026 = re.search(
        r"HEIGHT\s+(?P<height>\d+[\'’][0-9.]+[\"”])\s+(?P<weight>\d{3})\s*lbs\s+WEIGHT\s+"
        r"(?P<handedness>Left|Right|L|R)\s+(?P<birth_date>\d{4}-\d{2}-\d{2}).+?"
        r"(?P<position>[A-Z]{1,3}(?:/[A-Z]{1,3})?)\s+POSITION\(S\)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match_2026:
        bio.update(
            {
                "position": normalize_pdf_position(match_2026.group("position")),
                "handedness": normalize_handedness(match_2026.group("handedness")),
                "height_text": match_2026.group("height"),
                "height_cm": str(height_to_cm(match_2026.group("height"))),
                "weight_kg": str(pounds_to_kg(match_2026.group("weight"))),
                "birth_date": match_2026.group("birth_date"),
            }
        )
    return bio


def extract_stat_rows(text: str, *, draft_year: int) -> list[dict[str, str]]:
    season = extract_statistics_season(text) or f"{draft_year - 1}-{str(draft_year)[-2:]}"
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        goalie_match = re.match(
            r"^(?P<label>.+?)\s+(?P<games>\d+)\s+(?P<gaa>[0-9.]+)\s+"
            r"(?P<save_percentage>\.?\d{3})\s+(?P<shutouts>\d+)$",
            line.strip(),
        )
        if goalie_match:
            label = goalie_match.group("label").strip()
            team, league = split_team_league(label)
            if team and league:
                rows.append(
                    {
                        "season": season,
                        "league": league,
                        "team": team,
                        "games": goalie_match.group("games"),
                        "goals_against_average": goalie_match.group("gaa"),
                        "save_percentage": normalize_save_percentage(
                            goalie_match.group("save_percentage")
                        ),
                        "shutouts": goalie_match.group("shutouts"),
                    }
                )
            continue

        stat_match = re.match(
            r"^(?P<label>.+?)\s+(?P<games>\d+)\s+(?P<goals>\d+)\s+(?P<assists>\d+)\s+"
            r"(?P<points>\d+)\s+(?P<gpg>[0-9.]+)\s+(?P<apg>[0-9.]+)\s+(?P<ppg>[0-9.]+)$",
            line.strip(),
        )
        if not stat_match:
            continue
        label = stat_match.group("label").strip()
        team, league = split_team_league(label)
        if not team or not league:
            continue
        rows.append(
            {
                "season": season,
                "league": league,
                "team": team,
                "games": stat_match.group("games"),
                "goals": stat_match.group("goals"),
                "assists": stat_match.group("assists"),
                "points": stat_match.group("points"),
            }
        )
    return rows


def build_stat_line(
    player_id: str,
    row: dict[str, str],
    *,
    source_id: str,
    source_url: str,
) -> dict[str, str]:
    if row.get("save_percentage") or row.get("goals_against_average"):
        return {
            "player_id": player_id,
            "season": row["season"],
            "league": normalize_league_name(row["league"]),
            "team": row["team"],
            "games": row["games"],
            "goals": "",
            "assists": "",
            "points": "",
            "age": "",
            "timing": "pre_draft",
            "regular_season": "true",
            "source": "eliteprospects_pdf",
            "source_id": source_id,
            "source_url": source_url,
            "goalie_minutes": "",
            "shots_against": "",
            "saves": "",
            "goals_against": "",
            "save_percentage": row.get("save_percentage", ""),
            "goals_against_average": row.get("goals_against_average", ""),
            "wins": "",
            "losses": "",
            "ties": "",
            "shutouts": row.get("shutouts", ""),
        }
    return {
        "player_id": player_id,
        "season": row["season"],
        "league": normalize_league_name(row["league"]),
        "team": row["team"],
        "games": row["games"],
        "goals": row["goals"],
        "assists": row["assists"],
        "points": row["points"],
        "age": "",
        "timing": "pre_draft",
        "regular_season": "true",
        "source": "eliteprospects_pdf",
        "source_id": source_id,
        "source_url": source_url,
        "goalie_minutes": "",
        "shots_against": "",
        "saves": "",
        "goals_against": "",
        "save_percentage": "",
        "goals_against_average": "",
        "wins": "",
        "losses": "",
        "ties": "",
        "shutouts": "",
    }


def normalize_save_percentage(value: str) -> str:
    normalized = value.strip()
    return f"0{normalized}" if normalized.startswith(".") else normalized


def split_team_league(label: str) -> tuple[str, str]:
    parenthesized = re.match(r"^(?P<team>.+?)\s+\((?P<league>[^)]+)\)$", label)
    if parenthesized:
        return parenthesized.group("team").strip(), parenthesized.group("league").strip()
    parts = label.rsplit(" ", maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", ""


def extract_statistics_season(text: str) -> str:
    match = re.search(r"(\d{4}-\d{2})\s+STATISTICS", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def extract_tool_grades(text: str) -> dict[str, str]:
    match = re.search(
        r"Tool Grades\s*\(1\.0 to 9\.0\)\s+(?P<values>.+?)\s+Skating\s+Shooting"
        r"\s+Passing\s+Handling\s+Sense\s+Physical",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    values = [value.replace(" ", "") for value in re.findall(r"\d\.\s*\d", match.group("values"))]
    return dict(zip(TOOL_LABELS, values, strict=False))


def extract_grade(text: str) -> str:
    match_2026 = re.search(r"\n(?P<grade>[ABCDF])\nBADGES\nGRADE", text)
    if match_2026:
        return match_2026.group("grade")
    match_2025 = re.search(
        r"Tool Grades\s*\(1\.0 to 9\.0\).+?\s(?P<grade>[ABCDF])\s+Skating\s+Shooting",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match_2025.group("grade") if match_2025 else ""


def extract_rank_range(text: str) -> str:
    match = re.search(r"(?:Range:|RANK RANGE)\s*(\d+\s*-\s*\d+)", text, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def extract_rank(text: str, *, rank_range: str) -> str:
    match_2025 = re.search(r"\n(?P<rank>\d{1,3})\nShades of", text, flags=re.IGNORECASE)
    if match_2025:
        return match_2025.group("rank")
    match_2026 = re.search(r"^.+?SHADES OF\.\.\..*?(?P<rank>\d{1,3})\s*$", text.splitlines()[0])
    if match_2026:
        return match_2026.group("rank")
    return rank_range.split("-")[0].strip() if rank_range else ""


def extract_shades_of(text: str) -> str:
    match = re.search(r"SHADES OF\.\.\.\s*(?P<value>.+?)(?:\n|$)", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"Shades of\.\.\.\s*(?P<value>.+?)(?:\n|$)", text)
    if not match:
        return ""
    return re.sub(r"\d{1,3}$", "", clean_text(match.group("value"))).strip()


def extract_badges(text: str, *, grade: str) -> list[str]:
    badges: list[str] = []
    match_2025 = re.search(
        r"\d{3}\s*lbs\s+[LR]\d+[\'’][0-9.]+[\"”]\s+\d{4}-\d{2}-\d{2}\n"
        r"(?P<badges>.+?)\n\d{1,3}\nShades",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match_2025:
        badges.extend(extract_badge_tokens(match_2025.group("badges"), grade=grade))

    match_2026_primary = re.search(
        r"\n(?P<badge>[A-Z][A-Za-z ]{2,40})\n[ABCDF]\nBADGES\nGRADE",
        text,
    )
    if match_2026_primary:
        badges.append(clean_text(match_2026_primary.group("badge")))

    match_2026_more = re.search(
        r"(?:SKATING|PHYSICAL)\s*(?P<badges>.+?)\s*PROSPECT PROFILE",
        text,
        flags=re.DOTALL,
    )
    if match_2026_more:
        badges.extend(extract_badge_tokens(match_2026_more.group("badges"), grade=grade))

    return sorted(set(badge for badge in badges if badge))


def extract_badge_tokens(value: str, *, grade: str) -> list[str]:
    tokens: list[str] = []
    for line in value.splitlines():
        line = clean_text(line)
        if not line or line == grade:
            continue
        if line.upper() in {"SKATING", "SHOOTING", "PASSING", "HANDLING", "SENSE", "PHYSICAL"}:
            continue
        if len(line) <= 40:
            tokens.append(line)
    return tokens


def extract_profile_summary(text: str) -> str:
    match_2025 = re.search(
        r"Elevator Pitch\s+(?P<summary>.+?)\s+Tool Grades",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match_2025:
        return clean_text(match_2025.group("summary"))
    match_2026 = re.search(
        r"PROSPECT SUMMARY\s+(?P<summary>.+?)\s+(?:SHOOTING|2025-\d{2}\s+STATISTICS)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return clean_text(match_2026.group("summary")) if match_2026 else ""


def extract_profile_text(text: str, *, name: str) -> str:
    pipe_marker = f"|{name}"
    if pipe_marker in text:
        return clean_text(
            text.split(pipe_marker, maxsplit=1)[0].replace("NHL DRAFT GUIDE 2025", "")
        )
    match = re.search(
        r"POSITION\(S\)\s+(?P<body>.+?)\s+(?:SKATING|PROSPECT SUMMARY)",
        text,
        flags=re.DOTALL,
    )
    if match:
        return clean_text(match.group("body"))
    return ""


def profile_to_player_row(profile: EliteProspectsPdfProfile) -> dict[str, str]:
    return {
        "player_id": profile.player_id,
        "name": profile.name,
        "birth_date": profile.birth_date,
        "nationality": "",
        "position": profile.position,
        "handedness": profile.handedness,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "age_at_draft": "",
        "source": "eliteprospects_pdf",
        "source_id": f"{profile.draft_year}-ep-pdf-page-{profile.page_start}",
        "source_url": profile.source_url,
    }


def profile_to_ranking_row(profile: EliteProspectsPdfProfile) -> dict[str, str]:
    return {
        "player_id": profile.player_id,
        "draft_year": str(profile.draft_year),
        "source": "eliteprospects_pdf",
        "rank": profile.rank,
        "scope": "eliteprospects_draft_guide",
        "position": profile.position,
        "source_id": f"{profile.draft_year}-ep-pdf-page-{profile.page_start}",
        "source_url": profile.source_url,
    }


def profile_to_profile_row(profile: EliteProspectsPdfProfile) -> dict[str, str]:
    return {
        "player_id": profile.player_id,
        "draft_year": str(profile.draft_year),
        "name": profile.name,
        "page_start": str(profile.page_start),
        "page_end": str(profile.page_end),
        "rank": profile.rank,
        "rank_range": profile.rank_range,
        "grade": profile.grade,
        "position": profile.position,
        "handedness": profile.handedness,
        "height_text": profile.height_text,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "birth_date": profile.birth_date,
        "shades_of": profile.shades_of,
        "badges": "; ".join(profile.badges),
        "profile_summary": profile.profile_summary,
        "profile_text_chars": str(len(profile.profile_text)),
        "extraction_warnings": "; ".join(profile.extraction_warnings),
        "source": "eliteprospects_pdf",
        "source_id": f"{profile.draft_year}-ep-pdf-page-{profile.page_start}",
        "source_url": profile.source_url,
    }


def format_pdf_extraction_report(export: EliteProspectsPdfExport) -> str:
    profiles_with_stats = sum(1 for profile in export.profiles if profile.stat_lines)
    profiles_with_tools = sum(1 for profile in export.profiles if profile.tool_grades)
    vision_input_tokens = sum_ints(row.get("input_tokens", "") for row in export.vision_usage_rows)
    vision_output_tokens = sum_ints(row.get("output_tokens", "") for row in export.vision_usage_rows)
    vision_total_tokens = sum_ints(row.get("total_tokens", "") for row in export.vision_usage_rows)
    warning_counts: dict[str, int] = {}
    for profile in export.profiles:
        for warning in profile.extraction_warnings:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
    lines = [
        "# Elite Prospects PDF Extraction",
        "",
        "## Summary",
        f"- profiles: {len(export.profiles)}",
        f"- players: {len(export.players)}",
        f"- stat_lines: {len(export.season_stat_lines)}",
        f"- profiles_with_stats: {profiles_with_stats}",
        f"- profiles_with_tool_grades: {profiles_with_tools}",
        f"- player_index_rows: {len(export.index_rows)}",
        f"- vision_calls: {len(export.vision_usage_rows)}",
        f"- vision_input_tokens: {vision_input_tokens}",
        f"- vision_output_tokens: {vision_output_tokens}",
        f"- vision_total_tokens: {vision_total_tokens}",
        "",
        "## Warnings",
    ]
    if warning_counts:
        lines.extend(f"- {warning}: {count}" for warning, count in sorted(warning_counts.items()))
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def sum_ints(values: object) -> int:
    total = 0
    for value in values:
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_pdf_position(value: str) -> str:
    return value.replace("/", "").upper()


def normalize_handedness(value: str) -> str:
    normalized = value.strip().upper()
    if normalized == "LEFT":
        return "L"
    if normalized == "RIGHT":
        return "R"
    return normalized[:1]


def height_to_cm(value: str) -> int:
    normalized = value.replace("’", "'").replace("”", '"')
    match = re.match(r"(?P<feet>\d+)'(?P<inches>[0-9.]+)", normalized)
    if not match:
        return 0
    inches = int(match.group("feet")) * 12 + float(match.group("inches"))
    return round(inches * 2.54)


def pounds_to_kg(value: str) -> int:
    return round(int(value) * 0.453592) if value else 0
