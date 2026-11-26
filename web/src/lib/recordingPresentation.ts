import type { RecordingEntry, RecordingReview, RecordingStatus, StructuredFieldKey } from "@/types/report";

export const STATUS_LABEL: Record<RecordingStatus, string> = { new: "미검토", flagged: "조치 필요", reviewed: "검토 완료", trashed: "휴지통" };
/**
 * 정리 항목 4개. options 의 key 는 서버 분류 값(backend/app/domain/taxonomy/v1.yaml), label 은 화면 표시용이다.
 * 검토 저장(/api/reviews)에는 label 을, 이슈 수정(/api/issues PATCH)에는 key 를 보낸다.
 */
export const FIELD_CONFIG: Record<StructuredFieldKey, { label: string; description: string; serverField: string; options: readonly string[]; keys: Readonly<Record<string, string>> }> = {
  roadType: { label: "장소", description: "이슈가 생긴 곳의 도로 모양", serverField: "road_type", options: ["교차로", "곡선로", "합류로", "직선로", "횡단보도"], keys: { intersection: "교차로", curve: "곡선로", merge: "합류로", straight: "직선로", crosswalk: "횡단보도" } },
  previousAction: { label: "이전 동작", description: "이슈 직전에 내 차가 하던 동작", serverField: "ego_action_before", options: ["직진", "차선 변경", "좌회전", "우회전", "유턴", "정차 중"], keys: { going_straight: "직진", lane_change: "차선 변경", left_turn: "좌회전", right_turn: "우회전", u_turn: "유턴", stopped: "정차 중" } },
  targetType: { label: "대상 유형", description: "이슈와 관련된 대상", serverField: "target_type", options: ["차량", "보행자", "이륜차", "없음", "미확인"], keys: { vehicle: "차량", pedestrian: "보행자", two_wheeler: "이륜차", none: "없음", unknown: "미확인" } },
  reaction: { label: "반응", description: "이슈 이후 내 차가 보인 반응", serverField: "ego_reaction", options: ["급감속", "급가속", "과조향", "정차"], keys: { hard_decel: "급감속", hard_accel: "급가속", oversteer: "과조향", stop: "정차" } },
};

/** 서버 분류 값 → 화면 이름 */
export function labelForKey(field: StructuredFieldKey, key: string | null | undefined) {
  return key ? FIELD_CONFIG[field].keys[key] ?? null : null;
}

/** 화면 이름 → 서버 분류 값 (기타 직접 입력은 null) */
export function keyForLabel(field: StructuredFieldKey, label: string | undefined) {
  if (!label) return null;
  return Object.entries(FIELD_CONFIG[field].keys).find(([, value]) => value === label)?.[0] ?? null;
}

// TODO(차량 연동): 시뮬레이터라 차량 로그가 없다. 아래 값은 모든 녹음에 같은 예시로 보여 주며 저장하지 않는다.
export const DEMO_VEHICLE_DATA = [
  { label: "차선 유형", value: "차선" },
  { label: "위도·경도", value: "37.566500, 126.978000" },
  { label: "차가 하던 동작", value: "직진" },
  { label: "대상 유형", value: "보행자" },
  { label: "횡저크", value: "0.2 m/s³" },
  { label: "종저크", value: "-0.8 m/s³" },
  { label: "속도", value: "30 km/h" },
] as const;
export const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";
export const dateText = (value: string) => new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric" }).format(new Date(value));
export const timeText = (value: string) => new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
export const recordingTitle = (record: RecordingEntry) => record.review?.title || `${timeText(record.recordedAt)} 주행 이슈 녹음`;
export const recordingStatus = (record: RecordingEntry): RecordingStatus => record.trashedAt ? "trashed" : record.review?.status ?? "new";
/** 목록에 보여 줄 위치. 주소 변환은 하지 않고 좌표를 그대로 보여 준다. */
export function locationText(record: RecordingEntry) {
  const location = record.location;
  return location?.status === "available" ? `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}` : "위치 없음";
}
export function recordingSummary(record: RecordingEntry) {
  const review = reviewFor(record);
  return (Object.keys(FIELD_CONFIG) as StructuredFieldKey[]).map(key => review.fields[key]?.trim() || `${FIELD_CONFIG[key].label} ${review.otherFields?.includes(key) ? "기타" : "미입력"}`).join(" / ");
}
/** 저장된 검토가 없으면 서버가 자동 정리한 값으로 시작한다. 정리 값이 없으면 빈 칸이다. */
export function reviewFor(record: RecordingEntry): RecordingReview {
  return record.review ?? { id: record.id, title: "", status: "new", note: "", fields: { ...record.analysis.fields } };
}
