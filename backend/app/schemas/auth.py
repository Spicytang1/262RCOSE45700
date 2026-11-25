from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.login_code import LOGIN_CODE_RULE

Role = Literal["operator", "admin"]


class UserPublic(BaseModel):
    id: uuid.UUID
    display_name: str
    role: Role
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "display_name": "오퍼레이터1",
                    "role": "operator",
                    "is_active": True,
                }
            ]
        },
    )


class LoginRequest(BaseModel):
    code: str = Field(
        min_length=1,
        max_length=128,
        description=f"로그인 코드. 이 값 하나로 로그인합니다. {LOGIN_CODE_RULE}",
    )

    model_config = ConfigDict(json_schema_extra={"examples": [{"code": "operator1"}]})


class UserCreate(BaseModel):
    code: str = Field(min_length=8, max_length=64, description=f"로그인 코드. {LOGIN_CODE_RULE}")
    display_name: str = Field(min_length=1, max_length=100)
    role: Role

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"code": "operator6", "display_name": "오퍼레이터6", "role": "operator"}]}
    )


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    is_active: bool | None = None
    code: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description=f"새 로그인 코드로 교체합니다. 해당 사용자의 모든 세션이 폐기됩니다. {LOGIN_CODE_RULE}",
    )


class MeUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class CodeChange(BaseModel):
    current_code: str = Field(min_length=1, max_length=128, description="지금 쓰는 로그인 코드")
    new_code: str = Field(min_length=8, max_length=64, description=f"새 로그인 코드. {LOGIN_CODE_RULE}")


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="access token 유효 시간(초)")
    user: UserPublic

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example",
                    "token_type": "bearer",
                    "expires_in": 900,
                    "user": {
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "display_name": "오퍼레이터1",
                        "role": "operator",
                        "is_active": True,
                    },
                }
            ]
        }
    )
