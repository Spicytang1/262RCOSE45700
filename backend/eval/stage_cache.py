"""단계별 JSON 캐시. 지문(fingerprint)이 같으면 그 단계와 입력은 다시 호출하지 않는다."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_stage(
    path: Path,
    fingerprint: str,
    compute: Callable[[], dict[str, object]],
) -> tuple[dict[str, object], bool]:
    cached = read_stage(path)
    if cached is not None and cached.get("fingerprint") == fingerprint:
        payload = cached.get("payload")
        if isinstance(payload, dict):
            return payload, False
    payload = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"fingerprint": fingerprint, "payload": payload}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload, True


def read_stage(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    return loaded
