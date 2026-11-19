"""FactChat 게이트웨이 HTTP 클라이언트.

base URL 예: https://factchat.mindlogic-kr-api.com/v1/gateway
인증: Authorization: Bearer <GATEWAY_API_KEY>

STT, 이후의 chat/completions, decisions 가 이 클라이언트를 같이 쓴다.
경로는 base 기준 상대 경로다. 예: audio/transcriptions/, chat/completions/, decisions/

경로는 그대로 붙인다. `/` 와 `:` 는 인코딩하지 않는다. operation_id 의 콜론은
학교 게이트웨이 폴링에서 인코딩 없이 동작했다. 그 외 예약 문자는 percent-encoding 한다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from urllib.parse import quote

import httpx

from app.adapters.gateway.errors import GatewayError
from app.config import Settings

logger = logging.getLogger(__name__)

# Retry-After 가 비정상적으로 커도 요청 한 건이 이 시간 이상 멈추지 않게 한다.
MAX_RETRY_AFTER_SECONDS = 30.0

FormData = Mapping[str, str]


def build_url(base_url: str, path: str) -> httpx.URL:
    base = httpx.URL(base_url.rstrip("/"))
    suffix = quote(path.lstrip("/"), safe="/:")
    raw_path = base.raw_path.split(b"?", 1)[0].rstrip(b"/") + b"/" + suffix.encode("ascii")
    return base.copy_with(raw_path=raw_path)


class GatewayClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 120,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))
        self._max_retries = max_retries
        self._backoff = retry_backoff_seconds
        self._transport = transport
        self._sleep = sleep or time.sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> GatewayClient:
        return cls(
            settings.gateway_base_url,
            settings.gateway_api_key,
            timeout_seconds=settings.gateway_timeout_seconds,
            max_retries=settings.gateway_max_retries,
            retry_backoff_seconds=settings.gateway_retry_backoff_seconds,
        )

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        """chat/completions, decisions 같은 JSON POST."""
        body = self._send("POST", path, json_body=payload)
        if not isinstance(body, dict):
            raise GatewayError("게이트웨이 JSON 응답이 아닙니다.")
        return body

    def post_bytes(self, path: str, payload: dict[str, object]) -> bytes:
        """TTS 처럼 본문이 JSON 이 아닌 응답."""
        body = self._send("POST", path, json_body=payload, raw=True)
        if not isinstance(body, bytes):
            raise GatewayError("게이트웨이 바이너리 응답이 아닙니다.")
        return body

    def get_json(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, object]:
        return self._send("GET", path, params=params)

    def post_multipart(
        self,
        path: str,
        *,
        file_field: str,
        filename: str,
        content: bytes,
        content_type: str,
        data: FormData,
    ) -> dict[str, object]:
        files = {file_field: (filename, content, content_type)}
        return self._send("POST", path, data=data, files=files)

    def _send(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
        params: dict[str, str] | None = None,
        data: FormData | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        raw: bool = False,
    ) -> dict[str, object] | bytes:
        self._require_config()
        url = build_url(self.base_url, path)
        request_kwargs: dict[str, object] = {}
        if json_body is not None:
            request_kwargs["json"] = json_body
        if params is not None:
            request_kwargs["params"] = params
        if data is not None:
            request_kwargs["data"] = data
        if files is not None:
            request_kwargs["files"] = files

        # 재시도 동안 클라이언트를 닫지 않는다. 닫으면 전달받은 transport 까지 닫힐 수 있다.
        with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
            last_error: GatewayError | None = None
            for attempt in range(self._max_retries + 1):
                try:
                    response = client.request(
                        method,
                        url,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        follow_redirects=False,
                        **request_kwargs,
                    )
                except httpx.TimeoutException:
                    last_error = GatewayError(f"게이트웨이 요청 시간이 초과되었습니다 ({method}).")
                except httpx.HTTPError:
                    # httpx 예외 문자열에는 Authorization 이 들어갈 수 있어 원인으로 잇지 않는다.
                    last_error = GatewayError(f"게이트웨이 연결에 실패했습니다 ({method}).")
                else:
                    if response.status_code == 429 or response.status_code >= 500:
                        # 문서상 시작 요청의 5xx 는 과금되지 않는다.
                        last_error = error_from_response(response)
                        if attempt >= self._max_retries:
                            raise last_error
                        logger.warning("게이트웨이 재시도 %s %s status=%s", method, path, response.status_code)
                        self._sleep(self._delay(attempt, response))
                        continue
                    if response.status_code >= 400:
                        raise error_from_response(response)
                    if raw:
                        return response.content
                    return _json_object(response)
                if attempt >= self._max_retries:
                    raise last_error
                logger.warning("게이트웨이 재시도 %s %s (연결 실패)", method, path)
                self._sleep(self._delay(attempt, None))
        raise last_error or GatewayError("게이트웨이 요청에 실패했습니다.")

    def _require_config(self) -> None:
        if not self.base_url.strip():
            raise GatewayError("GATEWAY_BASE_URL 이 비어 있습니다.")
        if not self._api_key.strip():
            raise GatewayError("GATEWAY_API_KEY 가 비어 있습니다.")

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            parsed = _retry_after_seconds(response.headers.get("Retry-After"))
            if parsed is not None:
                return min(parsed, MAX_RETRY_AFTER_SECONDS)
        return min(self._backoff * (2**attempt), MAX_RETRY_AFTER_SECONDS)


def error_from_response(response: httpx.Response) -> GatewayError:
    message = ""
    try:
        message = _message_from_body(response.json())
    except ValueError:
        message = ""
    if not message:
        text = response.text.strip().replace("\n", " ")
        message = text[:300] if text else "응답 본문 없음"
    return GatewayError(f"게이트웨이 오류 ({response.status_code}): {message}", status_code=response.status_code)


def _message_from_body(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail")
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    for key in ("error", "message"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _json_object(response: httpx.Response) -> dict[str, object]:
    try:
        body = response.json()
    except ValueError:
        raise GatewayError(f"게이트웨이 응답이 JSON 이 아닙니다 ({response.status_code}).") from None
    if not isinstance(body, dict):
        raise GatewayError(f"게이트웨이 응답이 객체가 아닙니다 ({response.status_code}).")
    return body


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None
