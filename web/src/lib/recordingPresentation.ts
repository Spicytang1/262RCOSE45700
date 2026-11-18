import type { RecordingEntry, RecordingReview, RecordingStatus, StructuredFieldKey } from "@/types/report";

export const STATUS_LABEL: Record<RecordingStatus, string> = { new: "미검토", flagged: "조치 필요", reviewed: "검토 완료" };
export const FIELD_CONFIG: Record<StructuredFieldKey, { label: string; description: string; options: readonly string[] }> = {
  roadType: { label: "장소", description: "이슈가 생긴 곳의 도로 모양", options: ["교차로", "곡선로", "합류로", "직선로", "횡단보도"] },
  previousAction: { label: "이전 동작", description: "이슈 직전에 내 차가 하던 동작", options: ["직진", "차선 변경", "좌회전", "우회전", "정차 중"] },
  targetType: { label: "대상 유형", description: "이슈와 관련된 대상", options: ["차량", "보행자", "이륜차", "없음", "미확인"] },
  reaction: { label: "반응", description: "이슈 이후 내 차가 보인 반응", options: ["급감속", "급가속", "과조향", "정차"] },
};
// 사용자 지정 시연용 결과. 실제 음성 분석이나 차량에서 수집한 값이 아니다.
// TODO(backend): 녹음별 전사 결과를 서버에서 받아 사용한다. 처리 중·실패·결과 없음은 이 고정 문장으로 대신하지 않는다.
export const DEMO_TRANSCRIPT = "직진하는데 보행자 튀어나와서 수동감속했음";
// TODO(backend): 목록 표시와 검색에 함께 쓰는 임시 주소다. 실제 연결 시 녹음별 주소 응답으로 교체한다.
export const DEMO_ADDRESS = "XX동 XX로";
// TODO(backend): 녹음 시각·회차에 연결된 차량 로그 응답으로 교체한다. 기기에서 얻은 녹음 위치와 별개다.
// 아래 값은 모든 녹음에 동일하게 표시하는 예시다. 원본·검토 기록에 저장하거나 실제 지도 핀으로 사용하지 않는다.
export const DEMO_VEHICLE_DATA = [
  { label: "차선 유형", value: "차선" },
  { label: "위도·경도", value: "37.566500, 126.978000" },
  { label: "차가 하던 동작", value: "직진" },
  { label: "대상 유형", value: "보행자" },
  { label: "횡저크", value: "0.2 m/s³" },
  { label: "종저크", value: "-0.8 m/s³" },
  { label: "속도", value: "30 km/h" },
] as const;
// TODO(backend): 장소·이전 동작·대상 유형·반응을 녹음별 분석/차량 연동 결과로 교체한다. 사용자 수정 값과 분석 원본은 구분한다.
const DEMO_FIELDS = { roadType: "직선로", previousAction: "직진", targetType: "보행자", reaction: "급감속" };
export const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";
export const dateText = (value: string) => new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric" }).format(new Date(value));
export const timeText = (value: string) => new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
export const recordingTitle = (record: RecordingEntry) => record.review?.title || `${timeText(record.recordedAt)} 주행 이슈 녹음`;
export function recordingSummary(record: RecordingEntry) {
  const review = reviewFor(record);
  return (Object.keys(FIELD_CONFIG) as StructuredFieldKey[]).map(key => review.fields[key]?.trim() || `${FIELD_CONFIG[key].label} ${review.otherFields?.includes(key) ? "기타" : "미입력"}`).join(" / ");
}
export function reviewFor(record: RecordingEntry): RecordingReview {
  // TODO(backend): 미입력 값을 DEMO_FIELDS로 채우지 말고 해당 녹음의 분석 결과 또는 빈 값으로 초기화한다.
  // 이 반환값은 목록 표시뿐 아니라 useReviewAutosave의 최초 자동 저장에도 사용되므로 예시가 실제 검토 값으로 저장되지 않게 한다.
  const review = record.review ?? { id: record.id, title: "", status: "new" as const, note: "", fields: {} };
  return { ...review, fields: { ...DEMO_FIELDS, ...review.fields } };
}
