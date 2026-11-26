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

/** 서버가 정리한 결과 중 화면에 보여 주는 값 */
export type RecordingAnalysis = {
  /** 장소·이전 동작·대상 유형·반응. 값은 화면 표시용 한국어 이름이다. */
  fields: Partial<Record<StructuredFieldKey, string>>;
  /** 확신이 낮아 확인이 필요한 항목 */
  needsReview: StructuredFieldKey[];
  cause: string | null;
  place: string | null;
  mentionedTime: string | null;
  /** "30초 전" 같은 말을 녹음 시각 기준으로 바꾼 추정 시각 */
  estimatedAt: string | null;
};

/** 서버에 보관된 녹음 1건 (= 이슈 1건) */
export type StoredRecording = {
  /** 녹음 ID. 검토 저장과 화면 주소에 쓴다. */
  id: string;
  /** 이슈 ID. 휴지통·음성·정리 결과 수정에 쓴다. */
  issueId: string;
  supervisorId: SupervisorId;
  recordedAt: string;
  durationSec: number;
  sessionId?: string;
  location?: RecordingLocation;
  startTrigger?: RecordingStartTrigger;
  /** 받아쓴 글 (용어 보정 후) */
  transcript: string;
  analysis: RecordingAnalysis;
  issueStatus: "draft" | "confirmed" | "error";
  /** 서버 처리 중 실패한 단계 (받아쓰기·정리·분류) */
  pipelineErrors: string[];
  /** 음성 취소 판단 결과. review 면 사람이 확인해야 한다. */
  cancelDecision?: "trash" | "review" | "keep" | "skipped";
  trashedAt?: string;
};

/** 서버에 올리기 전, 방금 녹음한 원본 */
export type PendingRecording = {
  supervisorId: SupervisorId;
  audio: Blob;
  recordedAt: string;
  durationSec: number;
  sessionId: string;
  location?: RecordingLocation;
  startTrigger: RecordingStartTrigger;
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
