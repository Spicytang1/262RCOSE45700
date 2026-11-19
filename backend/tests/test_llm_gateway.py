from __future__ import annotations

import json

import httpx
import pytest
from app.adapters.classifier.gateway_jev import ClassificationFailed, GatewayJevClassifier
from app.adapters.extractor.gateway_claude import ExtractionFailed, GatewayClaudeExtractor
from app.adapters.gateway.client import GatewayClient
from app.adapters.gateway.errors import GatewayError
from app.config import Settings
from app.domain.jev_wording import load_jev_wording
from app.domain.taxonomy.loader import GUIDE_IDS, load_taxonomy
from app.domain.taxonomy.questions import build_questions

BASE = "https://factchat.mindlogic-kr-api.com/v1/gateway"
TRANSCRIPT = "강남대로에서 검은 차가 컷인해서 급제동했다."
EXTRACTED = {
    "cause": "컷인",
    "cause_evidence": "컷인해서",
    "location": "강남대로",
    "location_evidence": "없는장소",
    "mentioned_time": None,
    "mentioned_time_evidence": None,
}


def _client(handler) -> GatewayClient:
    return GatewayClient(BASE, "test-key", transport=httpx.MockTransport(handler), max_retries=0)


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def test_extract_uses_one_json_schema_call_and_drops_invented_evidence() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        content = json.dumps(EXTRACTED)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})

    extraction = GatewayClaudeExtractor(_client(handler), "claude-opus-5-5").extract(TRANSCRIPT)
    assert len(seen) == 1
    payload = _body(seen[0])
    assert str(seen[0].url).endswith("/chat/completions/")
    assert payload["model"] == "claude-opus-5-5"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert payload["messages"][1]["content"] == TRANSCRIPT
    assert "컷인" in payload["messages"][0]["content"]
    assert extraction.cause.value == "컷인"
    assert extraction.cause.evidence == "컷인해서"
    assert extraction.location.value is None
    assert extraction.mentioned_time.value is None


def test_json_schema_rejection_falls_back_once() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(
                400,
                json={"detail": {"code": 400, "message": "response_format json_schema is not supported"}},
            )
        fenced = "```json\n" + json.dumps(EXTRACTED) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": fenced}}]})

    extraction = GatewayClaudeExtractor(_client(handler), "claude-opus-5-5").extract(TRANSCRIPT)
    assert len(seen) == 2
    assert "response_format" not in _body(seen[1])
    assert extraction.cause.value == "컷인"


def test_invalid_json_is_repaired_once() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        content = "not-json" if len(seen) == 1 else json.dumps(EXTRACTED)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    GatewayClaudeExtractor(_client(handler), "claude-opus-5-5").extract(TRANSCRIPT)
    assert len(seen) == 2
    messages = _body(seen[1])["messages"]
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "not-json"
    assert messages[3]["role"] == "user"


def test_repair_failure_does_not_call_a_third_time() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "still bad"}}]})

    with pytest.raises(ExtractionFailed):
        GatewayClaudeExtractor(_client(handler), "claude-opus-5-5").extract(TRANSCRIPT)
    assert len(seen) == 2


def test_auth_failure_is_not_retried_as_schema_fallback() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, json={"detail": {"message": "Invalid API key"}})

    with pytest.raises(GatewayError):
        GatewayClaudeExtractor(_client(handler), "claude-opus-5-5").extract(TRANSCRIPT)
    assert len(seen) == 1


def test_summarize_is_one_plain_completion() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "이번 기간 이슈는 2건입니다."}}]})

    text = GatewayClaudeExtractor(_client(handler), "claude-opus-5-5").summarize(
        {"count": 2, "previous_count": 1, "delta": 1, "by_event_type": {"cut_in": 2}, "by_cause": {}}
    )
    assert text == "이번 기간 이슈는 2건입니다."
    payload = _body(seen[0])
    assert "response_format" not in payload
    assert "2" in payload["messages"][1]["content"]
    assert len(seen) == 1


def test_decisions_sends_every_question_once_and_maps_choice() -> None:
    seen: list[httpx.Request] = []
    questions = build_questions()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        incoming = _body(request)["questions"]
        answers = {}
        for question_id in incoming:
            choice = {"event_type": "cut_in", "severity": "high", "ego_action_before": "u_turn"}.get(
                question_id, next(iter(incoming[question_id]["criteria"]))
            )
            answers[question_id] = {
                "type": "choice",
                "choice": choice,
                "confidence": 0.91,
                "probabilities": {choice: 0.8} if choice != "u_turn" else {"going_straight": 0.4},
            }
        return httpx.Response(
            200,
            json={"id": "decisions-1", "object": "decisions", "model": "jev-1.14.0", "answers": answers},
        )

    result = GatewayJevClassifier(_client(handler), "jev-1.14.0").classify("강남대로 컷인", questions)
    assert len(seen) == 1
    payload = _body(seen[0])
    assert str(seen[0].url).endswith("/decisions/")
    assert payload["model"] == "jev-1.14.0"
    assert payload["state"] == "강남대로 컷인"
    assert set(payload["questions"]) == {"event_type", "severity", *GUIDE_IDS}
    assert all(item["type"] == "choice" for item in payload["questions"].values())
    assert "끼어들기" in payload["questions"]["event_type"]["criteria"]["cut_in"]
    assert "유턴" in payload["questions"]["ego_action_before"]["instructions"]
    by_id = {answer.id: answer for answer in result.answers}
    assert by_id["event_type"].value == "cut_in"
    assert by_id["event_type"].confidence == 0.91
    assert by_id["severity"].score == 2
    assert by_id["ego_action_before"].value is None


def test_jev_wording_matches_taxonomy_keys() -> None:
    wording = load_jev_wording()
    taxonomy = load_taxonomy()
    assert [item.key for item in taxonomy.event_types] == list(wording["event_type"].criteria)
    assert [item.key for item in taxonomy.severity_levels] == list(wording["severity"].criteria)
    for group_id, group in taxonomy.guide.items():
        assert [item.key for item in group.options] == list(wording[group_id].criteria)


def test_latest_jev_alias_is_rejected_before_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    with pytest.raises(ClassificationFailed):
        GatewayJevClassifier(_client(handler), "latest").classify("텍스트", build_questions())
    with pytest.raises(ValueError):
        Settings(_env_file=None, jev_model_version="latest")
