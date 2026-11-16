"""게이트웨이 호출 실패. 메시지에 API 키를 넣지 않는다."""

from __future__ import annotations


class GatewayError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
