from __future__ import annotations

import re

EMPLOYEE_NUMBER_PATTERN = re.compile(r"^[0-9]{4,12}$")


def is_employee_number(value: str) -> bool:
    return EMPLOYEE_NUMBER_PATTERN.fullmatch(value) is not None
