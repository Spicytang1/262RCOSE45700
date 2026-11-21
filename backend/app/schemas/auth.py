from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.employee_number import is_employee_number


class UserPublic(BaseModel):
    id: uuid.UUID
    username: str
    employee_number: str
    display_name: str
    role: Literal["operator", "admin"]

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(min_length=4, max_length=12, description="회사 식별 번호")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal["operator", "admin"]

    @field_validator("username")
    @classmethod
    def username_is_employee_number(cls, value: str) -> str:
        if not is_employee_number(value):
            raise ValueError("회사 식별 번호는 숫자 4자리에서 12자리입니다.")
        return value


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Literal["operator", "admin"] | None = None
    is_active: bool | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
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
                        "username": "1001",
                        "employee_number": "1001",
                        "display_name": "오퍼레이터1",
                        "role": "operator",
                    },
                }
            ]
        }
    )
