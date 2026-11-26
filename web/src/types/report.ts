/** 목록에서 받은 고유 번호를 사용한다. 기존 숫자 ID도 그대로 유지한다. */
export type SupervisorId = number | string;

export type Supervisor = {
  id: SupervisorId;
  name: string;
  photoUrl: string | null;
};

export type DriveSession = {
  id: string;
  supervisorId: SupervisorId;
  number: number;
  startedAt: string;
  endedAt: string | null;
};

export type RecordingStatus = "new" | "reviewed" | "flagged" | "trashed";
export type StructuredFieldKey = "roadType" | "previousAction" | "targetType" | "reaction";
export type RecordingReview = {
  id: string;
  title: string;
  status: RecordingStatus;
  /** 휴지통 복구 시 원래 검토 상태로 돌리기 위한 값이다. */
  previousStatusBeforeTrash?: "new" | "reviewed" | "flagged";
  trashedAt?: string;
  note: string;
  /** 이전 수기 항목도 지우지 않고 보존한다. */
  fields: Partial<Record<StructuredFieldKey | "location" | "event" | "situation" | "weather", string>>;
  otherFields?: StructuredFieldKey[];
  /** 다른 선택지로 바꿔도 마지막 기타 입력을 항목별로 보관한다. 기존 기록에는 없을 수 있다. */
  otherFieldValues?: Partial<Record<StructuredFieldKey, string>>;
};
export type RecordingEntry = StoredRecording & { review?: RecordingReview };

/** 녹음 버튼을 누를 때 요청한 기기 위치. 사건 시각의 차량 위치와는 다르다. */
export type RecordingLocation = { requestedAt: string } & (
  | { status: "available"; latitude: number; longitude: number; accuracy: number; capturedAt: string }
  | { status: "denied" | "timeout" | "unavailable" | "unsupported" | "insecure" }
);

/**
 * 녹음이 시작된 방식.
 * - button: 사용자가 앱에서 녹음 버튼을 직접 누름
 * - intervention: 차량의 수동 개입(핸들·브레이크 등)으로 자동 시작됨 (차량 연동 전까지 실제로 발생하지 않음)
 */
export type RecordingStartTrigger = "button" | "intervention";

/** 재생용 URL 대신 녹음 원본 자체를 보관한다. */
export type StoredRecording = {
  id: string;
  supervisorId: SupervisorId;
  recordedAt: string;
  durationSec: number;
  audio: Blob;
  /** 기존 녹음에는 없으며, 회차를 임의 배정하지 않는다. */
  sessionId?: string;
  /** 이전 녹음에는 위치가 없다. 상세를 열 때 현재 위치로 덮어쓰지 않는다. */
  location?: RecordingLocation;
  /** 녹음 시작 방식. 이전 녹음에는 없으며, 없으면 "기록 없음"으로 표시한다. */
  startTrigger?: RecordingStartTrigger;
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
