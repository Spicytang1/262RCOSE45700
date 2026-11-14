import type { RecordingEntry, RecordingReview, RecordingStatus, StructuredFieldKey } from "@/types/report";

export const STATUS_LABEL: Record<RecordingStatus, string> = { new: "미검토", reviewed: "검토 완료", flagged: "조치 필요" };
export const FIELD_CONFIG: Record<StructuredFieldKey, { label: string; description: string; options: readonly string[] }> = {
  roadType: { label: "장소", description: "이슈가 난 곳의 도로 모양", options: ["교차로", "곡선로", "합류로", "직선로", "횡단보도"] },
  previousAction: { label: "이전 동작", description: "이슈 직전에 내 차가 하던 동작", options: ["직진", "차선 변경", "좌회전", "우회전", "정차 중"] },
  targetType: { label: "대상 유형", description: "이슈와 관련된 대상", options: ["차량", "보행자", "이륜차", "없음", "미확인"] },
  reaction: { label: "반응", description: "이슈 이후 내 차가 보인 반응", options: ["급감속", "급가속", "과조향", "정차"] },
};
// 사용자 지정 시연용 결과. 실제 음성 분석이나 차량에서 수집한 값이 아니다.
export const DEMO_TRANSCRIPT = "직진하는데 보행자 튀어나와서 수동감속했음";
const DEMO_FIELDS = { roadType: "직선로", previousAction: "직진", targetType: "보행자", reaction: "급감속" };
export const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";
export const dateText = (value: string) => new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric" }).format(new Date(value));
export const timeText = (value: string) => new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
export const recordingTitle = (record: RecordingEntry) => record.review?.title || `${timeText(record.recordedAt)} 주행 이슈 녹음`;
export function reviewFor(record: RecordingEntry): RecordingReview {
  const review = record.review ?? { id: record.id, title: "", status: "new" as const, note: "", fields: {} };
  return { ...review, fields: { ...DEMO_FIELDS, ...review.fields } };
}
