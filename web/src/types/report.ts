/** 녹음 한 개 (재생용 URL + 녹음 길이) */
export type AudioClip = {
  url: string;
  label: string;
  /** 녹음 시간(초). webm은 브라우저가 길이를 못 읽는 경우가 있어 녹음할 때 직접 잰 값을 쓴다 */
  durationSec: number;
};

/** 자동 정리된 항목 하나 */
export type ReviewField = {
  value: string;
  /** 이 값을 뽑아낸 근거 발화 (없으면 null) */
  evidence: string | null;
};

/** 기록 확인 화면에 보여줄 데이터 */
export type ReviewData = {
  report_id: string;
  recorded_at: string;
  /** STT 결과 */
  transcript: string;
  /** 필드 구조화 결과 */
  fields: Record<string, ReviewField>;
};
