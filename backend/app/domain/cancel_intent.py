"""녹음 취소 의도 질문. 보고서 분류(taxonomy)와 따로 둔다."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.adapters.classifier.base import ChoiceOption, ChoiceQuestion
from app.domain.jev_wording import QuestionWording

CANCEL_QUESTION_ID = "cancel_intent"
CANCEL = "cancel"
KEEP = "keep"


class CancelOptionSpec(BaseModel):
    key: str
    label: str
    criteria: str
    keywords: list[str] = []


class CancelIntentSpec(BaseModel):
    id: str
    label: str
    instructions: str
    options: list[CancelOptionSpec]

    @property
    def wording(self) -> QuestionWording:
        return QuestionWording(
            instructions=self.instructions,
            criteria={option.key: option.criteria for option in self.options},
        )

    def keywords(self, key: str) -> list[str]:
        for option in self.options:
            if option.key == key:
                return option.keywords
        return []


def cancel_intent_path() -> Path:
    return Path(__file__).with_name("cancel_intent.yaml")


@lru_cache
def load_cancel_intent() -> CancelIntentSpec:
    raw = yaml.safe_load(cancel_intent_path().read_text(encoding="utf-8"))
    spec = CancelIntentSpec.model_validate(raw)
    keys = [option.key for option in spec.options]
    if spec.id != CANCEL_QUESTION_ID or keys != [CANCEL, KEEP]:
        raise ValueError(f"cancel_intent.yaml 구성이 다릅니다: id={spec.id} 보기={keys}")
    return spec


def build_cancel_question() -> ChoiceQuestion:
    spec = load_cancel_intent()
    return ChoiceQuestion(
        id=spec.id,
        prompt=spec.instructions.strip(),
        options=[ChoiceOption(key=option.key, description=option.criteria) for option in spec.options],
    )
