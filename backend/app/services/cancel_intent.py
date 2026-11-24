"""녹음 취소 의도 판단과 휴지통 처리.

STT 텍스트를 Jev 에 먼저 물어 이 녹음을 취소하려는 건지 본다.
- cancel 확률 >= CANCEL_CONF_HIGH: 휴지통(소프트 삭제). 뒤쪽 추출·분류는 하지 않는다.
- CANCEL_CONF_LOW 이상: 그대로 처리하고 cancel_intent 에 검토 필요를 단다.
- 그 밖: 그대로 처리.
판단이 실패해도 신고는 막지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.adapters.classifier.base import ChoiceAnswer
from app.adapters.classifier.factory import get_classifier
from app.adapters.classifier.gateway_jev import ClassificationFailed
from app.adapters.gateway.errors import GatewayError
from app.config import Settings
from app.domain.cancel_intent import CANCEL, CANCEL_QUESTION_ID, build_cancel_question
from app.models import Issue
from app.models.base import utcnow
from app.schemas.common import Classified

Decision = Literal["trash", "review", "keep", "skipped"]


@dataclass
class CancelCheck:
    decision: Decision
    classified: Classified[str] = field(default_factory=Classified[str])
    probability: float | None = None
    error: str | None = None

    @property
    def trash(self) -> bool:
        return self.decision == "trash"

    def meta(self, settings: Settings, *, trashed: bool) -> dict[str, object]:
        meta: dict[str, object] = {
            "decision": self.decision,
            "probability": self.probability,
            "thresholds": {"high": settings.cancel_conf_high, "low": settings.cancel_conf_low},
            "trashed": trashed,
        }
        if self.error:
            meta["error"] = self.error
        return meta


def cancel_probability(answer: ChoiceAnswer) -> float | None:
    if CANCEL in answer.probabilities:
        return answer.probabilities[CANCEL]
    if answer.confidence is None or answer.value is None:
        return None
    return answer.confidence if answer.value == CANCEL else 1.0 - answer.confidence


def decide(probability: float | None, settings: Settings) -> Decision:
    if probability is None:
        return "keep"
    if probability >= settings.cancel_conf_high:
        return "trash"
    if probability >= settings.cancel_conf_low:
        return "review"
    return "keep"


def check_cancel_intent(settings: Settings, text: str) -> CancelCheck:
    if not settings.cancel_intent_enabled or not text.strip():
        return CancelCheck(decision="skipped")
    try:
        result = get_classifier(settings).classify(text, [build_cancel_question()])
    except (GatewayError, ClassificationFailed) as exc:
        return CancelCheck(decision="skipped", error=str(exc)[:500])
    answer = next(
        (item for item in result.answers if isinstance(item, ChoiceAnswer) and item.id == CANCEL_QUESTION_ID),
        None,
    )
    if answer is None:
        return CancelCheck(decision="skipped", error="cancel_intent 답이 없습니다.")
    probability = cancel_probability(answer)
    decision = decide(probability, settings)
    classified = Classified[str](
        value=answer.value,
        probabilities=answer.probabilities,
        confidence=answer.confidence,
        needs_review=decision == "review",
    )
    return CancelCheck(decision=decision, classified=classified, probability=probability)


def move_to_trash(issue: Issue) -> bool:
    """이슈를 휴지통으로 보낸다. 소프트 삭제 컬럼(deleted_at)이 있을 때만 값을 채운다."""
    if not hasattr(Issue, "deleted_at"):
        return False
    issue.deleted_at = utcnow()
    return True
