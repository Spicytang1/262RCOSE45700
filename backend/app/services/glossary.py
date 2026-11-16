from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class GlossaryReplacement(BaseModel):
    source: str
    target: str
    requires_any: list[str] = []
    requires_none: list[str] = []


class Glossary(BaseModel):
    terms: list[str]
    replacements: list[GlossaryReplacement]
    fuzzy_threshold: float = 0.84


def glossary_path() -> Path:
    return Path(__file__).resolve().parents[1] / "domain" / "glossary.yaml"


@lru_cache
def load_glossary() -> Glossary:
    raw = yaml.safe_load(glossary_path().read_text(encoding="utf-8"))
    pairs = [
        GlossaryReplacement(
            source=item["from"],
            target=item["to"],
            requires_any=list(item.get("requires_any") or []),
            requires_none=list(item.get("requires_none") or []),
        )
        for item in raw["replacements"]
    ]
    pairs.sort(key=lambda item: len(item.source), reverse=True)
    threshold = float(raw.get("fuzzy_threshold", 0.84))
    return Glossary(terms=list(raw["terms"]), replacements=pairs, fuzzy_threshold=threshold)


_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = "ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def decompose_jamo(text: str) -> str:
    pieces: list[str] = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            syllable = code - 0xAC00
            pieces.append(_CHO[syllable // 588])
            pieces.append(_JUNG[(syllable % 588) // 28])
            jong = syllable % 28
            if jong:
                pieces.append(_JONG[jong - 1])
        else:
            pieces.append(char)
    return "".join(pieces)


def jamo_similarity(left: str, right: str) -> float:
    left_jamo = decompose_jamo(left)
    right_jamo = decompose_jamo(right)
    if not left_jamo or not right_jamo:
        return 0.0
    distance = _edit_distance(left_jamo, right_jamo)
    return 1 - distance / max(len(left_jamo), len(right_jamo))


def _edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for index, current_item in enumerate(left, start=1):
        current = [index]
        for inner, other in enumerate(right, start=1):
            current.append(
                min(current[inner - 1] + 1, previous[inner] + 1, previous[inner - 1] + (current_item != other))
            )
        previous = current
    return previous[-1]


def apply_exact(text: str, glossary: Glossary | None = None) -> str:
    spec = glossary or load_glossary()
    corrected = text
    for rule in spec.replacements:
        corrected = _replace_with_context(corrected, rule)
    return corrected


def _replace_with_context(text: str, rule: GlossaryReplacement) -> str:
    if any(token and token in text for token in rule.requires_none):
        return text
    start = 0
    while True:
        index = text.find(rule.source, start)
        if index < 0:
            return text
        end = index + len(rule.source)
        if _context_allows(text, index, end, rule):
            text = text[:index] + rule.target + text[end:]
            start = index + len(rule.target)
        else:
            start = end


def _context_allows(text: str, start: int, end: int, rule: GlossaryReplacement) -> bool:
    if not rule.requires_any:
        return True
    window = text[max(0, start - 40) : end + 40]
    return any(token in window for token in rule.requires_any)


def apply_fuzzy(text: str, glossary: Glossary | None = None) -> str:
    spec = glossary or load_glossary()
    if spec.fuzzy_threshold >= 1:
        return text
    candidates: list[tuple[float, int, int, str]] = []
    for term in spec.terms:
        if len(term) < 2 or term in text:
            continue
        for length in (len(term) - 1, len(term), len(term) + 1):
            if length < 2:
                continue
            for start in range(0, len(text) - length + 1):
                window = text[start : start + length]
                if any(char.isspace() for char in window):
                    continue
                score = jamo_similarity(window, term)
                if score >= spec.fuzzy_threshold and window != term:
                    candidates.append((score, start, start + length, term))
    candidates.sort(key=lambda item: (-item[0], -(item[2] - item[1])))
    used = [False] * len(text)
    spans: list[tuple[int, int, str]] = []
    for _score, start, end, term in candidates:
        if any(used[start:end]):
            continue
        for index in range(start, end):
            used[index] = True
        spans.append((start, end, term))
    corrected = text
    for start, end, term in sorted(spans, reverse=True):
        corrected = corrected[:start] + term + corrected[end:]
    return corrected


def correct_text(text: str, glossary: Glossary | None = None) -> str:
    spec = glossary or load_glossary()
    return apply_fuzzy(apply_exact(text, spec), spec)
