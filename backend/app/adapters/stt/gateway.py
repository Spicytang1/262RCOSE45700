"""학교 FactChat 게이트웨이 STT.

확인된 호출 (2026-11-16, factchat.mindlogic-kr-api.com):

- POST audio/transcriptions/  multipart: file, model, language_hints, enable_speaker_diarization
- 200: {operation_id, status: processing, model, duration_seconds, credits_charged}
- GET audio/transcriptions/{operation_id}/  (operation_id 의 콜론은 인코딩하지 않음)
- status: processing | completed | failed
- completed: {text, segments: [{speaker, text, start_ms, end_ms}], duration_seconds}
- 용어 힌트·단어 신뢰도 필드는 없다. webm 은 400 이므로 호출 전에 wav 로 바꾼다.

필드 이름이 바뀌면 이 파일의 상수와 _transcript_from_body 만 고친다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from app.adapters.audio import NormalizedAudio, normalize_for_stt
from app.adapters.gateway.client import GatewayClient
from app.adapters.gateway.errors import GatewayError
from app.adapters.stt.base import STTAdapter, STTCapabilities, Transcript
from app.schemas.common import WordToken

SUBMIT_PATH = "audio/transcriptions/"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

FILE_FIELD = "file"
FORM_MODEL = "model"
FORM_LANGUAGE = "language_hints"
FORM_DIARIZATION = "enable_speaker_diarization"


def poll_path(operation_id: str) -> str:
    return f"audio/transcriptions/{operation_id}/"


def transcription_fields(*, model: str, language: str, diarization: bool) -> dict[str, str]:
    # httpx 는 data 가 dict 일 때만 multipart 필드로 보낸다. 리스트는 raw body 로 취급한다.
    fields: dict[str, str] = {FORM_MODEL: model}
    if language.strip():
        fields[FORM_LANGUAGE] = language.strip()
    fields[FORM_DIARIZATION] = "true" if diarization else "false"
    return fields


class GatewaySTT(STTAdapter):
    provider_name = "gateway"

    def __init__(
        self,
        client: GatewayClient,
        *,
        model: str = "stt-async-v5",
        language: str = "ko",
        diarization: bool = True,
        poll_interval_seconds: float = 2,
        poll_timeout_seconds: float = 300,
        max_audio_bytes: int = 25 * 1024 * 1024,
        ffmpeg_bin: str = "ffmpeg",
        normalizer: Callable[[Path], NormalizedAudio] | None = None,
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._language = language
        self._diarization = diarization
        self._poll_interval = poll_interval_seconds
        self._poll_timeout = poll_timeout_seconds
        self._max_audio_bytes = max_audio_bytes
        self._ffmpeg_bin = ffmpeg_bin
        self._normalize = normalizer or self._normalize_file
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic

    @property
    def capabilities(self) -> STTCapabilities:
        # 단어 시각은 세그먼트 구간을 글자 수 비율로 나눈 값이다. 신뢰도는 응답에 없다.
        return STTCapabilities(
            supports_hints=False,
            supports_word_confidence=False,
            supports_word_timestamps=True,
        )

    def transcribe(self, audio_path: Path, hints: list[str]) -> Transcript:
        # hints 는 용어 사전이다. 게이트웨이에는 용어 힌트 필드가 없어 보내지 않는다.
        del hints
        normalized = self._normalize(audio_path)
        try:
            started = self._client.post_multipart(
                SUBMIT_PATH,
                file_field=FILE_FIELD,
                filename=normalized.filename,
                content=normalized.path.read_bytes(),
                content_type=normalized.content_type,
                data=transcription_fields(
                    model=self._model,
                    language=self._language,
                    diarization=self._diarization,
                ),
            )
            operation_id = _operation_id(started)
            ready = _transcript_if_terminal(started, language=self._language)
            if ready is not None:
                return ready
            return self._poll(operation_id)
        finally:
            normalized.cleanup()

    def _poll(self, operation_id: str) -> Transcript:
        deadline = self._monotonic() + self._poll_timeout
        while True:
            body = self._client.get_json(poll_path(operation_id))
            ready = _transcript_if_terminal(body, language=self._language)
            if ready is not None:
                return ready
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise GatewayError("STT 결과를 기다리는 시간이 초과되었습니다.")
            self._sleep(min(self._poll_interval, remaining))

    def _normalize_file(self, audio_path: Path) -> NormalizedAudio:
        return normalize_for_stt(
            audio_path,
            max_bytes=self._max_audio_bytes,
            ffmpeg_bin=self._ffmpeg_bin,
        )


def _operation_id(body: dict[str, object]) -> str:
    operation_id = body.get("operation_id")
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise GatewayError("STT 시작 응답에 operation_id 가 없습니다.")
    return operation_id


def _transcript_if_terminal(body: dict[str, object], *, language: str) -> Transcript | None:
    status = body.get("status")
    if status == STATUS_PROCESSING:
        return None
    if status == STATUS_FAILED:
        error = body.get("error")
        detail = error.strip() if isinstance(error, str) and error.strip() else "원인 미상"
        raise GatewayError(f"STT 변환에 실패했습니다: {detail}")
    if status == STATUS_COMPLETED:
        return _transcript_from_body(body, language=language)
    raise GatewayError(f"STT 상태를 해석할 수 없습니다: {status}")


def _transcript_from_body(body: dict[str, object], *, language: str) -> Transcript:
    text = body.get("text")
    if not isinstance(text, str):
        raise GatewayError("STT 완료 응답에 text 가 없습니다.")
    return Transcript(
        text=text,
        words=words_from_segments(body.get("segments")),
        language=language,
        provider=GatewaySTT.provider_name,
    )


def words_from_segments(segments: object) -> list[WordToken]:
    if segments is None:
        return []
    if not isinstance(segments, list):
        raise GatewayError("STT segments 형식이 리스트가 아닙니다.")
    words: list[WordToken] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise GatewayError("STT segment 형식이 객체가 아닙니다.")
        text = segment.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        start_ms = _millis(segment.get("start_ms"), "start_ms")
        end_ms = _millis(segment.get("end_ms"), "end_ms")
        if end_ms < start_ms:
            end_ms = start_ms
        words.extend(_words_in_span(text.strip(), start_ms, end_ms))
    return words


def _words_in_span(text: str, start_ms: int, end_ms: int) -> list[WordToken]:
    tokens = text.split()
    if not tokens:
        return []
    start = start_ms / 1000
    end = end_ms / 1000
    weights = [max(len(token), 1) for token in tokens]
    total = sum(weights)
    cursor = start
    consumed = 0
    words: list[WordToken] = []
    for index, (token, weight) in enumerate(zip(tokens, weights, strict=True)):
        consumed += weight
        word_end = end if index == len(tokens) - 1 else start + (end - start) * consumed / total
        words.append(
            WordToken(
                text=token,
                start=round(cursor, 3),
                end=round(word_end, 3),
                confidence=None,
            )
        )
        cursor = word_end
    return words


def _millis(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise GatewayError(f"STT segment 의 {field} 값이 없습니다.")
    return int(value)
