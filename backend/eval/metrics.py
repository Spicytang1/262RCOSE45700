"""평가 지표. 라벨 목록은 호출 시점의 taxonomy 와 정답 JSON 을 따른다."""

from __future__ import annotations

from eval.common import cer, wer
from eval.stt_metrics import term_recall


def korean_cer(reference: str, hypothesis: str) -> float:
    return cer(_compact(reference), _compact(hypothesis))


def field_key(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("in_taxonomy") is False:
            return None
        key = value.get("key")
        return str(key) if key else None
    return str(value)


def classification_accuracy(pairs: list[tuple[str | None, str | None]]) -> float | None:
    comparable = [(gold, predicted) for gold, predicted in pairs]
    if not comparable:
        return None
    hits = sum(1 for gold, predicted in comparable if gold == predicted)
    return hits / len(comparable)


def _count_pairs(
    golds: list[str | None],
    predictions: list[str | None],
    label: str,
    *,
    gold_matches: bool,
    predicted_matches: bool,
) -> int:
    total = 0
    for gold, predicted in zip(golds, predictions, strict=True):
        gold_ok = (gold == label) if gold_matches else (gold != label)
        predicted_ok = (predicted == label) if predicted_matches else (predicted != label)
        if gold_ok and predicted_ok:
            total += 1
    return total


def macro_f1(golds: list[str | None], predictions: list[str | None], labels: list[str]) -> float:
    scores: list[float] = []
    for label in labels:
        true_positive = _count_pairs(golds, predictions, label, gold_matches=True, predicted_matches=True)
        false_positive = _count_pairs(golds, predictions, label, gold_matches=False, predicted_matches=True)
        false_negative = _count_pairs(golds, predictions, label, gold_matches=True, predicted_matches=False)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def confusion_matrix(
    golds: list[str | None],
    predictions: list[str | None],
    labels: list[str],
) -> dict[str, dict[str, int]]:
    keys = [*labels, None]
    matrix = {str(gold): {str(predicted): 0 for predicted in keys} for gold in keys}
    for gold, predicted in zip(golds, predictions, strict=True):
        matrix[str(gold)][str(predicted)] += 1
    return matrix


def extraction_match(expected: str | None, actual: str | None) -> bool:
    return _compact(expected or "") == _compact(actual or "")


def hallucination_rate(fields: list[tuple[str | None, str | None]], transcript: str) -> float | None:
    """값이 있는데 근거 구절이 전사에 없으면 환각으로 센다."""
    filled = [(value, evidence) for value, evidence in fields if value]
    if not filled:
        return None
    unsupported = sum(1 for _value, evidence in filled if not evidence or evidence not in transcript)
    return unsupported / len(filled)


def term_recall_or_none(reference: str, hypothesis: str, terms: list[str]) -> float | None:
    return term_recall(reference, hypothesis, terms)


def text_error_rates(reference: str, hypothesis: str) -> tuple[float, float]:
    return korean_cer(reference, hypothesis), wer(reference, hypothesis)


def _compact(text: str) -> str:
    return "".join(text.split())
