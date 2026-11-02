type Props = {
  text: string;
  /** 하이라이트할 근거 발화 목록 */
  highlights: string[];
};

type Segment = { text: string; marked: boolean };

/** 문장에서 근거 발화 부분만 표시할 수 있도록 조각으로 나눈다 (겹치는 구간은 앞쪽 우선) */
function splitByHighlights(text: string, highlights: string[]): Segment[] {
  const ranges = highlights
    .map((h) => ({ start: text.indexOf(h), end: text.indexOf(h) + h.length }))
    .filter((r) => r.start >= 0)
    .sort((a, b) => a.start - b.start);

  const segments: Segment[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start < cursor) continue;
    if (r.start > cursor) segments.push({ text: text.slice(cursor, r.start), marked: false });
    segments.push({ text: text.slice(r.start, r.end), marked: true });
    cursor = r.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), marked: false });
  return segments;
}

export default function Transcript({ text, highlights }: Props) {
  return (
    <p className="text-[16px] leading-[1.75] text-ink">
      {splitByHighlights(text, highlights).map((seg, i) =>
        seg.marked ? (
          <mark key={i} className="rounded-[4px] bg-kakao-soft px-0.5 font-semibold text-ink shadow-[inset_0_-2px_0_#fee500]">
            {seg.text}
          </mark>
        ) : (
          <span key={i}>{seg.text}</span>
        ),
      )}
    </p>
  );
}
