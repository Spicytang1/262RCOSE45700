from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
import pytest
from app.adapters.classifier.base import ChoiceAnswer, ClassificationResult, ClassifierAdapter
from app.adapters.classifier.gateway_jev import GatewayJevClassifier
from app.adapters.classifier.mock import MockClassifier
from app.adapters.gateway.client import GatewayClient
from app.config import Settings
from app.domain.cancel_intent import build_cancel_question
from app.models import Issue
from app.services import cancel_intent as cancel_service
from app.services import pipeline as pipeline_module
from app.services.cancel_intent import decide
from app.services.pipeline import run_pipeline
from sqlalchemy.orm import Session

# 녹음을 지워 달라는 말
CANCEL_TEXTS = [
    "방금 거 취소해",
    "이거 삭제해 줘",
    "아 잘못 눌렀어 지워 줘",
    "방금 녹음 취소할게",
]

# 신고 내용 안에 취소·삭제 같은 말이 들어간 경우. 휴지통으로 가면 안 된다.
REPORT_TEXTS = [
    "아까 끼어들어서 취소할 뻔했어",
    "강남대로에서 앞차가 차선 변경을 취소하고 다시 들어와서 급제동했다",
    "내비 경로가 취소돼서 교차로에서 급하게 우회전했다",
    "강남대로에서 검은 차가 컷인해서 급제동했다",
]


class FixedCancel(ClassifierAdapter):
    """cancel_intent 만 정해진 확률로 답한다. 나머지 질문은 mock 에 넘긴다."""

    def __init__(self, probability: float) -> None:
        self.probability = probability
        self.calls: list[list[str]] = []
        self._mock = MockClassifier()

    def classify(self, state_text, questions):
        self.calls.append([question.id for question in questions])
        if [question.id for question in questions] != ["cancel_intent"]:
            return self._mock.classify(state_text, questions)
        value = "cancel" if self.probability >= 0.5 else "keep"
        return ClassificationResult(
            answers=[
                ChoiceAnswer(
                    id="cancel_intent",
                    value=value,
                    probabilities={"cancel": self.probability, "keep": 1 - self.probability},
                    confidence=max(self.probability, 1 - self.probability),
                )
            ]
        )


def _audio(tmp_path: Path, text: str) -> Path:
    audio = tmp_path / f"{uuid.uuid4().hex}.wav"
    audio.write_bytes(b"")
    audio.with_name(f"{audio.stem}.transcript.txt").write_text(text, encoding="utf-8")
    return audio


def _run(db: Session, settings: Settings, tmp_path: Path, user_id: uuid.UUID, text: str) -> Issue:
    return run_pipeline(db, settings, user_id=user_id, audio_path=_audio(tmp_path, text), recorded_at=None)


def test_thresholds_split_trash_review_keep(settings: Settings) -> None:
    assert decide(0.9, settings) == "trash"
    assert decide(settings.cancel_conf_high, settings) == "trash"
    assert decide(0.6, settings) == "review"
    assert decide(0.2, settings) == "keep"
    assert decide(None, settings) == "keep"
    settings.cancel_conf_high = 0.95
    assert decide(0.9, settings) == "review"


@pytest.mark.parametrize("text", CANCEL_TEXTS)
def test_mock_cancels_request_speech(text: str) -> None:
    answer = MockClassifier().classify(text, [build_cancel_question()]).answers[0]
    assert answer.value == "cancel"
    assert answer.probabilities["cancel"] >= 0.85


@pytest.mark.parametrize("text", REPORT_TEXTS)
def test_mock_keeps_reports_with_cancel_words(text: str) -> None:
    answer = MockClassifier().classify(text, [build_cancel_question()]).answers[0]
    assert answer.value == "keep"
    assert answer.probabilities["cancel"] < 0.5


@pytest.mark.parametrize("text", CANCEL_TEXTS)
def test_cancel_speech_goes_to_trash_without_extraction(db, settings, tmp_path, accounts, monkeypatch, text) -> None:
    def no_extract(_settings):
        raise AssertionError("취소 녹음은 추출하지 않는다")

    monkeypatch.setattr(pipeline_module, "get_extractor", no_extract)
    issue = _run(db, settings, tmp_path, accounts["operator"], text)
    meta = issue.pipeline_meta["cancel_intent"]
    assert meta["decision"] == "trash"
    assert issue.status == "draft"
    assert issue.content == text
    extraction = issue.ai_extraction
    assert extraction["cancel_intent"]["value"] == "cancel"
    assert extraction["cause"]["value"] is None
    assert extraction["event_type"]["value"] is None
    assert extraction["mentioned_time_resolved"] is None
    soft_delete = hasattr(Issue, "deleted_at")
    assert meta["trashed"] is soft_delete
    if soft_delete:
        assert issue.deleted_at is not None


@pytest.mark.parametrize("text", REPORT_TEXTS)
def test_reports_with_cancel_words_stay(db, settings, tmp_path, accounts, text) -> None:
    issue = _run(db, settings, tmp_path, accounts["operator"], text)
    meta = issue.pipeline_meta["cancel_intent"]
    assert meta["decision"] == "keep"
    assert meta["trashed"] is False
    assert issue.ai_extraction["cancel_intent"]["value"] == "keep"
    assert issue.ai_extraction["cancel_intent"]["needs_review"] is False
    assert issue.ai_extraction["event_type"]["probabilities"]
    if hasattr(Issue, "deleted_at"):
        assert issue.deleted_at is None


def test_ambiguous_cancel_needs_review_and_keeps_report(db, settings, tmp_path, accounts, monkeypatch) -> None:
    fake = FixedCancel(0.6)
    monkeypatch.setattr(cancel_service, "get_classifier", lambda _settings: fake)
    issue = _run(db, settings, tmp_path, accounts["operator"], "강남대로에서 컷인해서 급제동했다 아 근데 이거 취소")
    meta = issue.pipeline_meta["cancel_intent"]
    assert meta["decision"] == "review"
    assert meta["probability"] == 0.6
    assert meta["trashed"] is False
    assert issue.ai_extraction["cancel_intent"]["needs_review"] is True
    assert issue.ai_extraction["event_type"]["value"] == "cut_in"


def test_threshold_comes_from_settings(db, settings, tmp_path, accounts, monkeypatch) -> None:
    monkeypatch.setattr(cancel_service, "get_classifier", lambda _settings: FixedCancel(0.9))
    settings.cancel_conf_high = 0.95
    issue = _run(db, settings, tmp_path, accounts["operator"], "방금 거 취소")
    assert issue.pipeline_meta["cancel_intent"]["decision"] == "review"
    assert issue.pipeline_meta["cancel_intent"]["thresholds"] == {"high": 0.95, "low": 0.5}


def test_disabled_skips_cancel_call(db, settings, tmp_path, accounts, monkeypatch) -> None:
    fake = FixedCancel(0.99)
    monkeypatch.setattr(cancel_service, "get_classifier", lambda _settings: fake)
    settings.cancel_intent_enabled = False
    issue = _run(db, settings, tmp_path, accounts["operator"], "방금 거 취소해")
    assert fake.calls == []
    assert issue.pipeline_meta["cancel_intent"]["decision"] == "skipped"
    assert issue.ai_extraction["cancel_intent"]["value"] is None


def test_cancel_check_failure_does_not_block_report(db, settings, tmp_path, accounts) -> None:
    settings.classifier_provider = "gateway_jev"
    settings.gateway_api_key = ""
    issue = _run(db, settings, tmp_path, accounts["operator"], "강남대로에서 컷인해서 급제동했다")
    meta = issue.pipeline_meta["cancel_intent"]
    assert meta["decision"] == "skipped"
    assert meta["error"]
    assert issue.ai_extraction["cause"]["value"] is not None


def test_jev_gets_cancel_question_alone() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "answers": {
                    "cancel_intent": {
                        "type": "choice",
                        "choice": "cancel",
                        "confidence": 0.93,
                        "probabilities": {"cancel": 0.93, "keep": 0.07},
                    }
                }
            },
        )

    client = GatewayClient("https://example.test/v1/gateway", "test-key", transport=httpx.MockTransport(handler))
    result = GatewayJevClassifier(client, "jev-1.14.0").classify("방금 거 취소해", [build_cancel_question()])
    question = seen[0]["questions"]
    assert list(question) == ["cancel_intent"]
    assert question["cancel_intent"]["type"] == "choice"
    assert list(question["cancel_intent"]["criteria"]) == ["cancel", "keep"]
    assert "취소할 뻔했어" in question["cancel_intent"]["criteria"]["keep"]
    answer = result.answers[0]
    assert answer.value == "cancel"
    assert answer.probabilities == {"cancel": 0.93, "keep": 0.07}
