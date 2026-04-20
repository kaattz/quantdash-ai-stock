"""Skill Library 模块：解析 游资skills/ 目录下的 Markdown 文件，提供结构化 API。

前端通过 GET /integrations/skills/library 获取所有 skill 条目，
根据 scope 匹配场景后将 instructions 注入 LLM prompt。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import APIRouter

from server.models import SkillLibraryEntry, SkillLibraryResponse
from server.shared import runtime

ROUTER = APIRouter(tags=["skills"])
SKILL_LIBRARY_DIR = runtime.ROOT_DIR / "游资skills"
SKILL_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# 中文范围标签 → 前端 scope key 映射
SCOPE_LABEL_MAP = {
    "reportsummary": "reportSummary",
    "研报摘要": "reportSummary",
    "ai 研报摘要": "reportSummary",
    "dailyreview": "dailyReview",
    "盘后复盘": "dailyReview",
    "ai 当日复盘": "dailyReview",
    "ultrashortanalysis": "ultraShortAnalysis",
    "超短分析": "ultraShortAnalysis",
    "超短深度分析": "ultraShortAnalysis",
    "premarketplan": "premarketPlan",
    "盘前计划": "premarketPlan",
    "盘前预案": "premarketPlan",
    "stockobservation": "stockObservation",
    "个股观察": "stockObservation",
    "planvalidation": "planValidation",
    "计划校验": "planValidation",
    "次日校验": "planValidation",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return slug or "skill"


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _split_skill_sections(content: str) -> List[Tuple[str, str]]:
    matches = list(SKILL_SECTION_RE.finditer(content))
    sections: List[Tuple[str, str]] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        if not heading.lower().startswith("skill"):
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections.append((heading, content[start:end].strip()))
    return sections


def _extract_fenced_block(body: str, labels: List[str]) -> str:
    for label in labels:
        pattern = re.compile(
            rf"\*\*{re.escape(label)}\*\*\s*```(?:\w+)?\s*(.*?)```",
            re.DOTALL,
        )
        matched = pattern.search(body)
        if matched:
            return matched.group(1).strip()
    return ""


def _normalize_scopes(raw: str) -> List[str]:
    scopes: List[str] = []
    for line in raw.splitlines():
        value = line.strip().strip("-").strip()
        if not value:
            continue
        key = value.replace("`", "").strip().lower()
        normalized = SCOPE_LABEL_MAP.get(key) or SCOPE_LABEL_MAP.get(
            value.replace("`", "").strip()
        )
        if normalized and normalized not in scopes:
            scopes.append(normalized)
    return scopes


def _build_entry(
    file_path: Path, source_title: str, section_heading: str, body: str
) -> Optional[SkillLibraryEntry]:
    name = _extract_fenced_block(body, ["名称", "建议名称"]).splitlines()
    name_value = name[0].strip() if name else ""
    if not name_value:
        cleaned_heading = re.sub(
            r"^Skill\s*\d+\s*[：:]\s*", "", section_heading, flags=re.IGNORECASE
        )
        name_value = cleaned_heading.strip()

    instructions = _extract_fenced_block(
        body, ["规则文本", "instructions", "可直接放入 instructions"]
    )
    if not instructions:
        return None

    description = _extract_fenced_block(body, ["描述", "一句话描述"]).splitlines()
    description_value = description[0].strip() if description else ""
    scopes_value = _extract_fenced_block(body, ["建议范围", "建议 scopes"])

    return SkillLibraryEntry(
        id=f"library:{_slugify(file_path.stem)}:{_slugify(name_value)}",
        name=name_value,
        description=description_value,
        instructions=instructions,
        scopes=_normalize_scopes(scopes_value),
        fileName=file_path.name,
        sourceTitle=source_title,
        updatedAt=datetime.fromtimestamp(file_path.stat().st_mtime, tz=None).isoformat(),
        readOnly=True,
    )


def _load_skill_entries_from_file(file_path: Path) -> List[SkillLibraryEntry]:
    content = file_path.read_text(encoding="utf-8")
    title = _extract_title(content, file_path.stem)
    entries: List[SkillLibraryEntry] = []
    sections = _split_skill_sections(content)
    for heading, body in sections:
        entry = _build_entry(file_path, title, heading, body)
        if entry:
            entries.append(entry)
    if entries:
        return entries

    # 如果没有找到 Skill 章节，尝试把整个文件当作一个 skill
    fallback_entry = _build_entry(file_path, title, title, content)
    if fallback_entry:
        entries.append(fallback_entry)
    return entries


@ROUTER.get("/integrations/skills/library", response_model=SkillLibraryResponse)
async def get_skill_library() -> SkillLibraryResponse:
    """返回所有游资 skill 条目，前端根据 scope 筛选后注入 LLM prompt。"""
    if not SKILL_LIBRARY_DIR.exists():
        return SkillLibraryResponse(entries=[])

    entries: List[SkillLibraryEntry] = []
    for file_path in sorted(SKILL_LIBRARY_DIR.glob("*.md")):
        try:
            entries.extend(_load_skill_entries_from_file(file_path))
        except Exception as exc:
            runtime.LOGGER.warning(
                "Failed to load skill library file %s: %s", file_path.name, exc
            )

    return SkillLibraryResponse(entries=entries)
