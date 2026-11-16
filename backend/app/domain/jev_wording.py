"""Jev에 보내는 질문 문구. 보기 키는 taxonomy 와 맞춘다."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.domain.taxonomy.loader import GUIDE_IDS, Taxonomy, load_taxonomy


class QuestionWording(BaseModel):
    instructions: str = Field(min_length=1)
    criteria: dict[str, str]


def wording_path() -> Path:
    return Path(__file__).with_name("jev_questions.yaml")


@lru_cache
def load_jev_wording() -> dict[str, QuestionWording]:
    raw = yaml.safe_load(wording_path().read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("jev_questions.yaml 최상위는 질문별 객체여야 합니다.")
    wording = {str(key): QuestionWording.model_validate(value) for key, value in raw.items()}
    ensure_wording_covers_taxonomy(wording, load_taxonomy())
    return wording


def ensure_wording_covers_taxonomy(wording: dict[str, QuestionWording], taxonomy: Taxonomy) -> None:
    expected = {"event_type", "severity", *GUIDE_IDS}
    missing = expected - set(wording)
    extra = set(wording) - expected
    if missing or extra:
        raise ValueError(f"jev 질문 구성이 taxonomy 와 다릅니다. 없음={sorted(missing)} 추가={sorted(extra)}")
    _same_keys(
        "event_type",
        [item.key for item in taxonomy.event_types],
        wording["event_type"].criteria,
    )
    _same_keys(
        "severity",
        [item.key for item in taxonomy.severity_levels],
        wording["severity"].criteria,
    )
    for group_id, group in taxonomy.guide.items():
        _same_keys(group_id, [item.key for item in group.options], wording[group_id].criteria)


def _same_keys(question_id: str, expected: list[str], criteria: dict[str, str]) -> None:
    if list(criteria) != expected:
        raise ValueError(f"{question_id} 보기 순서가 taxonomy 와 다릅니다: {list(criteria)} != {expected}")
    blank = [key for key, text in criteria.items() if not str(text).strip()]
    if blank:
        raise ValueError(f"{question_id} 문구가 비어 있습니다: {blank}")
