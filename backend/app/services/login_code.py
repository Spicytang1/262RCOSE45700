from __future__ import annotations

import hashlib
import hmac
import re

from app.config import Settings

# 영문과 숫자를 모두 포함한 8자 이상. 이 코드 하나가 아이디이자 비밀번호다.
LOGIN_CODE_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]{8,64}$")
LOGIN_CODE_RULE = "로그인 코드는 영문과 숫자를 모두 포함한 8자 이상 64자 이하입니다."

_DEFAULT_KEY = b"issue-reporting-login-code-v1"


def is_login_code(value: str) -> bool:
    return LOGIN_CODE_PATTERN.fullmatch(value) is not None


def digest_login_code(code: str, settings: Settings) -> str:
    """코드 원문 대신 저장하고 조회에 쓰는 값. 같은 코드는 항상 같은 값이 나온다."""
    key = settings.login_code_pepper.encode("utf-8") or _DEFAULT_KEY
    return hmac.new(key, code.encode("utf-8"), hashlib.sha256).hexdigest()
