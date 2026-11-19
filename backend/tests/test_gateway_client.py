from __future__ import annotations

import httpx
import pytest
from app.adapters.gateway.client import GatewayClient
from app.adapters.gateway.errors import GatewayError

BASE = "https://factchat.mindlogic-kr-api.com/v1/gateway"
KEY = "super-secret-key"
OPERATION_ID = "soniox:d198ee67-8563-49fa-bf85-01f04aae8b58:265e99f2dba0c02b"


def _client(handler, **kwargs) -> GatewayClient:
    api_key = kwargs.pop("api_key", KEY)
    return GatewayClient(
        BASE,
        api_key,
        transport=httpx.MockTransport(handler),
        sleep=kwargs.pop("sleep", lambda _seconds: None),
        **kwargs,
    )


def test_post_json_sends_bearer_and_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "decisions-1", "object": "decisions"})

    body = _client(handler).post_json("decisions/", {"model": "jev-1.14.0", "state": "직진"})
    assert body["object"] == "decisions"
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url).endswith("/decisions/")
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["content-type"].startswith("application/json")
    assert b"jev-1.14.0" in request.content


def test_get_keeps_operation_id_colons() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"status": "processing"})

    _client(handler).get_json(f"audio/transcriptions/{OPERATION_ID}/")
    assert seen == [f"{BASE}/audio/transcriptions/{OPERATION_ID}/"]
    assert "%3A" not in seen[0]


def test_retries_500_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(502, json={"detail": {"code": 502, "message": "engine"}})
        return httpx.Response(200, json={"ok": True})

    sleeps: list[float] = []
    body = _client(handler, max_retries=3, retry_backoff_seconds=0.25, sleep=sleeps.append).get_json("models/")
    assert body == {"ok": True}
    assert calls["n"] == 3
    assert sleeps == [0.25, 0.5]


def test_retries_429_using_retry_after_then_stops() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "120"}, json={"detail": "Rate limit exceeded"})
        return httpx.Response(200, json={"ok": True})

    sleeps: list[float] = []
    _client(handler, max_retries=1, sleep=sleeps.append).post_json("chat/completions/", {"model": "x"})
    assert sleeps == [30.0]


def test_exhausted_500_raises_gateway_message_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": {"code": 500, "message": "upstream"}})

    with pytest.raises(GatewayError, match="upstream") as caught:
        _client(handler, max_retries=2, retry_backoff_seconds=0).post_json("chat/completions/", {"model": "x"})
    assert caught.value.status_code == 500
    assert KEY not in str(caught.value)


def test_400_is_not_retried_and_uses_detail_message() -> None:
    calls = {"n": 0}
    message = (
        "invalid_request_error - Could not read the duration of the uploaded audio. "
        "Send a container with duration metadata (mp3, m4a/mp4, wav, flac, ogg/opus, aiff)."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"detail": {"code": 400, "message": message}})

    with pytest.raises(GatewayError, match="Could not read the duration") as caught:
        _client(handler, max_retries=3).post_multipart(
            "audio/transcriptions/",
            file_field="file",
            filename="sample.webm",
            content=b"webm",
            content_type="audio/webm",
            data={"model": "stt-async-v5"},
        )
    assert calls["n"] == 1
    assert caught.value.status_code == 400
    assert KEY not in str(caught.value)


def test_redirect_is_not_followed() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(302, headers={"Location": "https://evil.example/steal"})

    with pytest.raises(GatewayError, match="302"):
        _client(handler, max_retries=3).get_json("credits/")
    assert calls["n"] == 1


def test_connection_error_retries_without_leaking_key() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("refused")

    with pytest.raises(GatewayError, match="연결에 실패") as caught:
        _client(handler, max_retries=1, retry_backoff_seconds=0).get_json("models/")
    assert calls["n"] == 2
    assert KEY not in str(caught.value)


def test_missing_key_and_base_url_do_not_call_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("요청이 나가면 안 됩니다")

    with pytest.raises(GatewayError, match="GATEWAY_API_KEY"):
        _client(handler, api_key="").get_json("models/")
    with pytest.raises(GatewayError, match="GATEWAY_BASE_URL"):
        GatewayClient("", KEY, transport=httpx.MockTransport(handler)).get_json("models/")
