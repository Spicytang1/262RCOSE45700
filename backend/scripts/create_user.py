from __future__ import annotations

import argparse
import os
import sys

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.services.login_code import LOGIN_CODE_RULE
from app.services.users import DuplicateLoginCodeError, InvalidLoginCodeError, add_user


def main() -> None:
    parser = argparse.ArgumentParser(description="사용자를 만듭니다. 로그인 코드는 환경변수에서 읽습니다.")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=["operator", "admin"], required=True)
    parser.add_argument("--code-env", required=True, help="로그인 코드가 들어 있는 환경변수 이름")
    args = parser.parse_args()
    code = os.environ.get(args.code_env, "")
    if not code:
        print(f"{args.code_env} 가 비어 있습니다.", file=sys.stderr)
        raise SystemExit(1)
    settings = get_settings()
    db = make_session_factory(make_engine(settings))()
    try:
        add_user(db, settings, code=code, display_name=args.display_name, role=args.role)
        db.commit()
    except InvalidLoginCodeError:
        print(LOGIN_CODE_RULE, file=sys.stderr)
        raise SystemExit(1) from None
    except DuplicateLoginCodeError:
        print("이미 사용 중인 로그인 코드입니다.", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        db.close()
    print(f"생성했습니다: {args.display_name}")


if __name__ == "__main__":
    main()
