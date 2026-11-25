from __future__ import annotations

import wave
from pathlib import Path

import httpx
import pytest
from app.adapters.audio import NormalizedAudio
from app.adapters.gateway.client import GatewayClient
from app.adapters.gateway.errors import GatewayError
from app.adapters.stt.factory import get_stt_adapter
from app.adapters.stt.gateway import GatewaySTT, _transcript_if_terminal, words_from_segments
from app.adapters.stt.mock import MockSTT
from app.api.errors import EXTERNAL_FAILED
from app.config import Settings
from fastapi.testclient import TestClient
from pydantic import ValidationError
from scripts.stt_smoke import main

from tests.conftest import OPERATOR_CODE, login, upload

BASE = "https://factchat.mindlogic-kr-api.com/v1/gateway"
KEY = "test-key"
OPERATION_ID = "soniox:d198ee67-8563-49fa-bf85-01f04aae8b58:265e99f2dba0c02b"
PROBE_TEXT = (
    "방금 교차로에서 직진하던 중에 왼쪽에서 검은 승용차가 컷인해서 앞으로 끼어들었어요. "
    "급제동했고, 제가 바로 테이크오버했습니다."
)
WEBM_ERROR = (
    "invalid_request_error - Could not read the duration of the uploaded audio. "
    "Send a container with duration metadata (mp3, m4a/mp4, wav, flac, ogg/opus, aiff)."
)


def _submit(model: str = "stt-async-v5") -> dict[str, object]:
    return {
        "operation_id": OPERATION_ID,
        "status": "processing",
        "model": model,
        "duration_seconds": 10.88,
        "credits_charged": 1.0880000000000003,
    }


def _completed() -> dict[str, object]:
    return {
        "operation_id": OPERATION_ID,
        "status": "completed",
        "duration_seconds": 10.88,
        "text": PROBE_TEXT,
        "segments": [
            {
                "speaker": "Speaker 1",
                "text": PROBE_TEXT,
                "start_ms": 390,
                "end_ms": 10470,
            }
        ],
    }


def _fake_normalizer(tmp_path: Path):
    def normalize(source: Path) -> NormalizedAudio:
        del source
        directory = tmp_path / "normalized"
        directory.mkdir()
        path = directory / "audio.wav"
        path.write_bytes(b"RIFF-normalized-wav")
        return NormalizedAudio(path=path, filename="audio.wav", content_type="audio/wav", directory=directory)

    return normalize


def _adapter(handler, tmp_path: Path, **kwargs) -> tuple[GatewaySTT, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = GatewayClient(
        BASE,
        KEY,
        transport=httpx.MockTransport(wrapped),
        max_retries=0,
        sleep=lambda _seconds: None,
    )
    adapter = GatewaySTT(
        client,
        poll_interval_seconds=kwargs.pop("poll_interval_seconds", 0),
        poll_timeout_seconds=kwargs.pop("poll_timeout_seconds", 30),
        normalizer=kwargs.pop("normalizer", _fake_normalizer(tmp_path)),
        sleep=kwargs.pop("sleep", lambda _seconds: None),
        monotonic=kwargs.pop("monotonic", lambda: 0.0),
        **kwargs,
    )
    return adapter, seen


def _field_value(body: str, name: str) -> str:
    marker = f'name="{name}"'
    start = body.index(marker)
    window = body[start : start + 160]
    # multipart 값은 헤더 다음 빈 줄 뒤에 있다.
    return window.split("\r\n\r\n", 1)[1].split("\r\n", 1)[0]


def test_transcribe_uses_probe_shapes(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=_submit())
        return httpx.Response(200, json=_completed())

    adapter, seen = _adapter(handler, tmp_path)
    audio = tmp_path / "sample.webm"
    audio.write_bytes(b"webm-bytes")
    transcript = adapter.transcribe(audio, ["컷인", "테이크오버"])

    assert transcript.text == PROBE_TEXT
    assert transcript.provider == "gateway"
    assert transcript.language == "ko"
    assert transcript.words[0].text == "방금"
    assert transcript.words[0].start == 0.390
    assert transcript.words[0].confidence is None
    assert transcript.words[-1].text == "테이크오버했습니다."
    assert transcript.words[-1].end == 10.470
    assert " ".join(word.text for word in transcript.words) == PROBE_TEXT
    assert all(word.confidence is None for word in transcript.words)

    post, get = seen
    assert post.method == "POST"
    assert str(post.url) == f"{BASE}/audio/transcriptions/"
    payload = post.content.decode("utf-8", errors="replace")
    assert _field_value(payload, "model") == "stt-async-v5"
    assert _field_value(payload, "language_hints") == "ko"
    assert _field_value(payload, "enable_speaker_diarization") == "true"
    assert 'name="file"' in payload
    assert "audio.wav" in payload
    assert "audio/wav" in payload
    assert b"RIFF-normalized-wav" in post.content
    assert "컷인" not in payload
    assert "테이크오버" not in payload
    assert post.headers["authorization"] == f"Bearer {KEY}"
    assert get.method == "GET"
    assert str(get.url) == f"{BASE}/audio/transcriptions/{OPERATION_ID}/"
    assert "%3A" not in str(get.url)
    assert not (tmp_path / "normalized").exists()


def test_model_v6_and_diarization_off(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=_submit("stt-async-v6"))
        return httpx.Response(200, json=_completed())

    adapter, seen = _adapter(handler, tmp_path, model="stt-async-v6", diarization=False)
    adapter.transcribe(tmp_path / "clip.wav", [])
    payload = seen[0].content.decode("utf-8", errors="replace")
    assert _field_value(payload, "model") == "stt-async-v6"
    assert _field_value(payload, "enable_speaker_diarization") == "false"


def test_polls_while_processing(tmp_path: Path) -> None:
    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=_submit())
        polls["n"] += 1
        if polls["n"] == 1:
            return httpx.Response(
                200,
                json={"operation_id": OPERATION_ID, "status": "processing", "duration_seconds": 10.88},
            )
        return httpx.Response(200, json=_completed())

    sleeps: list[float] = []
    adapter, seen = _adapter(handler, tmp_path, poll_interval_seconds=2, sleep=sleeps.append)
    transcript = adapter.transcribe(tmp_path / "clip.wav", [])
    assert transcript.text == PROBE_TEXT
    assert sleeps == [2]
    assert [request.method for request in seen] == ["POST", "GET", "GET"]


def test_poll_timeout(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=_submit())
        return httpx.Response(200, json={"operation_id": OPERATION_ID, "status": "processing"})

    adapter, seen = _adapter(handler, tmp_path, poll_timeout_seconds=0)
    with pytest.raises(GatewayError, match="초과"):
        adapter.transcribe(tmp_path / "clip.wav", [])
    assert [request.method for request in seen] == ["POST", "GET"]


def test_failed_poll_uses_error_field(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=_submit())
        return httpx.Response(
            200,
            json={
                "operation_id": OPERATION_ID,
                "status": "failed",
                "error": "Audio file could not be decoded",
            },
        )

    adapter, _seen = _adapter(handler, tmp_path)
    with pytest.raises(GatewayError, match="Audio file could not be decoded"):
        adapter.transcribe(tmp_path / "clip.wav", [])


def test_webm_rejection_shape_is_not_polled(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": {"code": 400, "message": WEBM_ERROR}})

    adapter, seen = _adapter(handler, tmp_path)
    with pytest.raises(GatewayError, match="Could not read the duration") as caught:
        adapter.transcribe(tmp_path / "sample.webm", [])
    assert caught.value.status_code == 400
    assert [request.method for request in seen] == ["POST"]


def test_real_ffmpeg_upload_is_16k_wav(tmp_path: Path) -> None:
    source = tmp_path / "mic.wav"
    with wave.open(str(source), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 1600)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json=_submit())
        return httpx.Response(200, json=_completed())

    adapter, seen = _adapter(handler, tmp_path, normalizer=None)
    adapter._normalize = adapter._normalize_file
    adapter.transcribe(source, [])
    uploaded = seen[0].content
    assert b"audio/wav" in uploaded
    assert (16000).to_bytes(4, "little") in uploaded
    assert b"webm" not in uploaded.lower()


def test_words_from_multiple_segments() -> None:
    words = words_from_segments(
        [
            {"speaker": "Speaker 1", "text": "급제동했다", "start_ms": 0, "end_ms": 1000},
            {"speaker": "Speaker 2", "text": "테이크오버", "start_ms": 1200, "end_ms": 1800},
        ]
    )
    assert [(word.text, word.start, word.end) for word in words] == [
        ("급제동했다", 0.0, 1.0),
        ("테이크오버", 1.2, 1.8),
    ]


def test_completed_without_text_raises() -> None:
    with pytest.raises(GatewayError, match="text"):
        _transcript_if_terminal({"status": "completed", "segments": []}, language="ko")


def test_factory_switches_provider() -> None:
    mock = get_stt_adapter(Settings(_env_file=None, stt_provider="mock"))
    assert isinstance(mock, MockSTT)
    gateway = get_stt_adapter(
        Settings(_env_file=None, stt_provider="gateway", gateway_api_key="k", stt_model="stt-async-v6")
    )
    assert isinstance(gateway, GatewaySTT)
    assert gateway.capabilities.supports_hints is False
    assert gateway.capabilities.supports_word_confidence is False
    assert gateway.capabilities.supports_word_timestamps is True
    with pytest.raises(ValidationError):
        Settings(_env_file=None, stt_model="stt-async-v4")


def test_gateway_failure_is_503_and_removes_audio(client: TestClient, app) -> None:
    app.state.settings.stt_provider = "gateway"
    app.state.settings.gateway_api_key = "test-key"

    def boom(self, audio_path: Path, hints: list[str]) -> None:
        del self, audio_path, hints
        raise GatewayError("down")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(GatewaySTT, "transcribe", boom)
    try:
        token = login(client, OPERATOR_CODE).json()["access_token"]
        response = upload(client, token)
    finally:
        monkeypatch.undo()
    assert response.status_code == 503
    assert response.json()["detail"] == EXTERNAL_FAILED
    storage = Path(app.state.settings.storage_dir)
    assert list(storage.iterdir()) == []


def test_smoke_skips_without_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    assert main([]) == 0
    assert main(["--text", "직진하다가 컷인"]) == 0
    assert "건너뜁니다" in capsys.readouterr().out
