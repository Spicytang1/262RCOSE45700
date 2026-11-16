"""게이트웨이 chat/completions 사실 추출.

한 녹음에 호출은 한 번이 기본이다. json_schema 를 거절하면(400) 프롬프트 JSON 으로
한 번 바꾸고, 그 결과가 스키마에 안 맞으면 수정을 한 번만 더 요청한다.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from app.adapters.extractor.base import Extraction, ExtractorAdapter, SummaryStatsPayload, TextFact
from app.adapters.gateway.client import GatewayClient
from app.adapters.gateway.errors import GatewayError
from app.services.glossary import load_glossary

logger = logging.getLogger(__name__)

CHAT_PATH = "chat/completions/"
EXTRACTION_MAX_TOKENS = 1024
SUMMARY_MAX_TOKENS = 512

EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "cause": {"type": ["string", "null"]},
        "cause_evidence": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "location_evidence": {"type": ["string", "null"]},
        "mentioned_time": {"type": ["string", "null"]},
        "mentioned_time_evidence": {"type": ["string", "null"]},
    },
    "required": [
        "cause",
        "cause_evidence",
        "location",
        "location_evidence",
        "mentioned_time",
        "mentioned_time_evidence",
    ],
}

SYSTEM_PROMPT = """너는 자율주행 시험 차량 안전 감독관 발화에서 사실만 뽑는다.
전사에 없는 원인, 장소, 시각을 만들지 마라. 모르면 null 이다.
cause_evidence, location_evidence, mentioned_time_evidence 는 전사에 그대로 있는 연속 구절만 쓴다. 없으면 null.
값은 그 구절 안에서만 짧게 정리한다. 도로 유형, 직전 동작, 대상, 반응은 뽑지 마라.
표준 용어가 있으면 그 표기를 쓴다: {terms}
JSON 객체만 반환한다."""

SUMMARY_SYSTEM = """주어진 집계 숫자만 한국어 한 문단으로 풀어 쓴다.
새 건수를 계산하거나, 입력에 없는 유형·원인을 만들지 마라.
숫자는 입력과 같아야 한다."""

REPAIR_INSTRUCTION = """이전 JSON 이 스키마와 맞지 않는다: {error}
전사에 없는 내용은 null 로 두고, 스키마의 키만 있는 JSON 객체만 다시 출력하라."""


class ExtractionFailed(Exception):
    pass


class ExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause: str | None
    cause_evidence: str | None
    location: str | None
    location_evidence: str | None
    mentioned_time: str | None
    mentioned_time_evidence: str | None


class GatewayClaudeExtractor(ExtractorAdapter):
    def __init__(self, client: GatewayClient, model: str) -> None:
        self._client = client
        self.model = model.strip()

    def extract(self, transcript_text: str) -> Extraction:
        if not transcript_text.strip():
            return _empty_extraction()
        if not self.model:
            raise ExtractionFailed("EXTRACT_MODEL 이 비어 있습니다.")
        messages = _extraction_messages(transcript_text)
        schema: dict[str, object] | None = EXTRACTION_SCHEMA
        try:
            raw = self._complete(messages, schema, EXTRACTION_MAX_TOKENS)
        except GatewayError as exc:
            if not _schema_rejected(exc):
                raise
            schema = None
            raw = self._complete(messages, None, EXTRACTION_MAX_TOKENS)
        try:
            return _to_extraction(raw, transcript_text)
        except ExtractionFailed as exc:
            logger.warning("추출 JSON 검증 실패로 1회 재요청합니다.")
            repair = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": REPAIR_INSTRUCTION.format(error=exc)},
            ]
            raw = self._complete(repair, schema, EXTRACTION_MAX_TOKENS)
            return _to_extraction(raw, transcript_text)

    def summarize(self, stats: dict[str, object]) -> str:
        if not self.model:
            raise ExtractionFailed("EXTRACT_MODEL 이 비어 있습니다.")
        payload = SummaryStatsPayload.model_validate(stats)
        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": json.dumps(payload.model_dump(), ensure_ascii=False)},
        ]
        text = self._complete(messages, None, SUMMARY_MAX_TOKENS).strip()
        if not text:
            raise GatewayError("요약 문장이 비어 있습니다.")
        return text

    def _complete(self, messages: list[dict[str, str]], schema: dict[str, object] | None, max_tokens: int) -> str:
        body = self._client.post_json(CHAT_PATH, _chat_payload(self.model, messages, schema, max_tokens))
        return _message_content(body)


def _chat_payload(
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, object] | None,
    max_tokens: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "issue_extraction", "strict": True, "schema": schema},
        }
    return payload


def _extraction_messages(transcript: str) -> list[dict[str, str]]:
    terms = ", ".join(load_glossary().terms)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(terms=terms)},
        {"role": "user", "content": transcript},
    ]


def _schema_rejected(exc: GatewayError) -> bool:
    if exc.status_code != 400:
        return False
    text = str(exc).lower()
    return any(hint in text for hint in ("response_format", "json_schema", "structured"))


def _message_content(body: dict[str, object]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise GatewayError("chat 응답에 choices 가 없습니다.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise GatewayError("chat 응답에 message 가 없습니다.")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    raise GatewayError("chat 응답 content 를 읽지 못했습니다.")


def _to_extraction(raw: str, transcript: str) -> Extraction:
    try:
        payload = ExtractionPayload.model_validate(_parse_json_object(raw))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ExtractionFailed(f"추출 JSON 이 스키마와 맞지 않습니다: {exc}") from None
    return Extraction(
        cause=_ground(payload.cause, payload.cause_evidence, transcript),
        location=_ground(payload.location, payload.location_evidence, transcript),
        mentioned_time=_ground(payload.mentioned_time, payload.mentioned_time_evidence, transcript),
    )


def _parse_json_object(raw: str) -> dict[str, object]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("JSON 객체가 아닙니다.")
    return parsed


def _ground(value: str | None, evidence: str | None, transcript: str) -> TextFact:
    cleaned = value.strip() if isinstance(value, str) else ""
    quote = evidence.strip() if isinstance(evidence, str) else ""
    if not quote or quote not in transcript:
        return TextFact()
    return TextFact(value=cleaned or None, evidence=quote)


def _empty_extraction() -> Extraction:
    return Extraction(cause=TextFact(), location=TextFact(), mentioned_time=TextFact())
