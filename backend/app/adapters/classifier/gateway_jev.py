"""게이트웨이 decisions 분류.

질문 문구는 app/domain/jev_questions.yaml 한 파일이다.
severity 도 확인된 choice 형식으로 묻고, 파이프라인이 기대하는 점수 인덱스로 되돌린다.
한 녹음당 questions 를 한 번에 보낸다.
"""

from __future__ import annotations

from app.adapters.classifier.base import (
    ChoiceAnswer,
    ChoiceQuestion,
    ClassificationResult,
    ClassifierAdapter,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
from app.adapters.gateway.client import GatewayClient
from app.domain.jev_wording import QuestionWording, load_jev_wording
from app.domain.taxonomy.loader import Taxonomy, load_taxonomy

DECISIONS_PATH = "decisions/"


class ClassificationFailed(Exception):
    pass


class GatewayJevClassifier(ClassifierAdapter):
    def __init__(self, client: GatewayClient, model_version: str, *, taxonomy: Taxonomy | None = None) -> None:
        self._client = client
        self.model_version = model_version.strip()
        self._taxonomy = taxonomy or load_taxonomy()
        self._wording = load_jev_wording()

    def classify(self, state_text: str, questions: list[Question]) -> ClassificationResult:
        if not state_text.strip():
            raise ClassificationFailed("분류할 텍스트가 비어 있습니다.")
        if not self.model_version or self.model_version.lower() == "latest":
            raise ClassificationFailed("JEV_MODEL_VERSION 이 비어 있거나 latest 입니다.")
        payload = {
            "model": self.model_version,
            "state": state_text,
            "questions": _decision_questions(questions, self._wording, self._taxonomy),
        }
        body = self._client.post_json(DECISIONS_PATH, payload)
        return _parse_answers(body, questions, self._taxonomy)


def _decision_questions(
    questions: list[Question],
    wording: dict[str, QuestionWording],
    taxonomy: Taxonomy,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    for question in questions:
        block = wording.get(question.id)
        if block is None:
            raise ClassificationFailed(f"질문 문구가 없습니다: {question.id}")
        if isinstance(question, ChoiceQuestion):
            criteria = {option.key: block.criteria[option.key] for option in question.options}
            _check_choice(question.id, criteria)
            payload[question.id] = {
                "type": "choice",
                "instructions": block.instructions.strip(),
                "criteria": criteria,
            }
            continue
        if isinstance(question, ScoreQuestion) and question.id == "severity":
            criteria = {level.key: block.criteria[level.key] for level in taxonomy.severity_levels}
            _check_choice(question.id, criteria)
            payload[question.id] = {
                "type": "choice",
                "instructions": block.instructions.strip(),
                "criteria": criteria,
            }
            continue
        raise ClassificationFailed(f"지원하지 않는 질문입니다: {question.id}")
    return payload


def _check_choice(question_id: str, criteria: dict[str, str]) -> None:
    if not 2 <= len(criteria) <= 255:
        raise ClassificationFailed(f"{question_id} 보기 수가 decisions choice 범위가 아닙니다.")


def _parse_answers(body: dict[str, object], questions: list[Question], taxonomy: Taxonomy) -> ClassificationResult:
    raw_answers = body.get("answers")
    if not isinstance(raw_answers, dict):
        raise ClassificationFailed("decisions 응답에 answers 가 없습니다.")
    answers: list[ChoiceAnswer | ScoreAnswer] = []
    for question in questions:
        raw = raw_answers.get(question.id)
        if isinstance(question, ChoiceQuestion):
            keys = [option.key for option in question.options]
            answers.append(_choice_answer(question.id, raw, keys))
        elif isinstance(question, ScoreQuestion) and question.id == "severity":
            keys = [level.key for level in taxonomy.severity_levels]
            answers.append(_severity_answer(raw, keys))
    return ClassificationResult(answers=answers)


def _choice_answer(question_id: str, raw: object, keys: list[str]) -> ChoiceAnswer:
    choice, probabilities, confidence = _choice_parts(raw)
    value = choice if choice in keys else None
    return ChoiceAnswer(
        id=question_id,
        value=value,
        probabilities=_known_probabilities(probabilities, keys),
        confidence=confidence,
    )


def _severity_answer(raw: object, keys: list[str]) -> ScoreAnswer:
    choice, probabilities, confidence = _choice_parts(raw)
    score = keys.index(choice) if choice in keys else None
    return ScoreAnswer(
        id="severity",
        score=score,
        distribution=_known_probabilities(probabilities, keys),
        confidence=confidence,
    )


def _choice_parts(raw: object) -> tuple[str | None, object, float | None]:
    if not isinstance(raw, dict):
        return None, {}, None
    if raw.get("type") not in (None, "choice"):
        raise ClassificationFailed("decisions 답 유형이 choice 가 아닙니다.")
    choice = raw.get("choice")
    if choice is not None and not isinstance(choice, str):
        raise ClassificationFailed("decisions choice 값이 문자열이 아닙니다.")
    confidence = raw.get("confidence")
    if confidence is not None and not isinstance(confidence, int | float):
        raise ClassificationFailed("decisions confidence 값이 숫자가 아닙니다.")
    return choice, raw.get("probabilities"), float(confidence) if confidence is not None else None


def _known_probabilities(raw: object, keys: list[str]) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    probabilities: dict[str, float] = {}
    allowed = set(keys)
    for key, value in raw.items():
        if key not in allowed or isinstance(value, bool) or not isinstance(value, int | float):
            continue
        probabilities[str(key)] = float(value)
    return probabilities
