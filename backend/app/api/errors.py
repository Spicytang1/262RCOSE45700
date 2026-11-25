from __future__ import annotations

from app.schemas.common import ErrorBody, UnprocessableBody

INVALID_AUTH = "인증이 유효하지 않습니다"
FORBIDDEN = "권한이 없습니다."
ISSUE_NOT_FOUND = "이슈를 찾을 수 없습니다."
DRIVE_NOT_FOUND = "운행 회차를 찾을 수 없습니다."
RECORDING_NOT_FOUND = "녹음을 찾을 수 없습니다."
USER_NOT_FOUND = "사용자를 찾을 수 없습니다."
DRIVE_NOT_OPEN = "진행 중인 본인 운행 회차가 아닙니다."
LOGIN_FAILED = "로그인 코드가 올바르지 않습니다"
CODE_MISMATCH = "현재 로그인 코드가 올바르지 않습니다."
CODE_DUPLICATE = "이미 사용 중인 로그인 코드입니다."
UPLOAD_TOO_LARGE = "오디오 파일이 너무 큽니다."
EXTERNAL_FAILED = "외부 호출에 실패했습니다. 다시 시도해 주세요."
ISSUE_TRASHED = "휴지통에 있는 이슈입니다. 복원한 뒤 수정하세요."
ISSUE_NOT_TRASHED = "휴지통에 넣은 이슈만 영구 삭제할 수 있습니다."
SUMMARY_FAILED = "요약 문장 생성에 실패했습니다. 다시 시도해 주세요."
INVALID_REQUEST = "요청 형식이 올바르지 않습니다"


def error_response(description: str) -> dict[str, object]:
    return {
        "model": ErrorBody,
        "description": description,
        "content": {"application/json": {"example": {"detail": description}}},
    }


RESP_401 = {401: error_response(INVALID_AUTH)}
RESP_403 = {403: error_response(FORBIDDEN)}
RESP_404 = {404: error_response(ISSUE_NOT_FOUND)}
RESP_413 = {413: error_response(UPLOAD_TOO_LARGE)}
RESP_503 = {503: error_response(EXTERNAL_FAILED)}

# 422 는 FastAPI 형식 검증(detail 이 배열)과 서버가 직접 거부한 경우(detail 이 문장)가 섞여 나온다.
RESP_422 = {
    422: {
        "model": UnprocessableBody,
        "description": INVALID_REQUEST,
    }
}
