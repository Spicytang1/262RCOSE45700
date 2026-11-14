export type SupervisorId = 1 | 2 | 3 | 4 | 5 | 6;

export type DriveSession = {
  id: string;
  supervisorId: SupervisorId;
  number: number;
  startedAt: string;
  endedAt: string | null;
};

export type RecordingStatus = "new" | "reviewed" | "flagged";
export type StructuredFieldKey = "roadType" | "previousAction" | "targetType" | "reaction";
export type RecordingReview = {
  id: string;
  title: string;
  status: RecordingStatus;
  note: string;
  /** 이전 수기 항목도 지우지 않고 보존한다. */
  fields: Partial<Record<StructuredFieldKey | "location" | "event" | "situation" | "weather", string>>;
  otherFields?: StructuredFieldKey[];
};
export type RecordingEntry = StoredRecording & { review?: RecordingReview };

/** 재생용 URL 대신 녹음 원본 자체를 보관한다. */
export type StoredRecording = {
  id: string;
  supervisorId: SupervisorId;
  recordedAt: string;
  durationSec: number;
  audio: Blob;
  /** 기존 녹음에는 없으며, 회차를 임의 배정하지 않는다. */
  sessionId?: string;
};

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
