import type { ReviewData } from "@/types/report";

// 실제 서버 연결 전까지 쓰는 임시 가짜 데이터
// TODO(backend): 기존 Review 화면의 전사·구조화·근거·시각·기록 ID가 모두 고정 예시다. 서버의 기록별 결과로 교체한다.
export const mockReview: ReviewData = {
  report_id: "report-001",
  recorded_at: "2026-10-30T14:20:00+09:00",

  // STT 결과
  transcript:
    "삼거리에서 좌회전하는데 누가 무단 횡단을 하려고 해서 급하게 멈췄어. 다행히 부딪히진 않았어.",

  // 필드 구조화 결과
  fields: {
    location: { value: "서울특별시 성북구 삼거리", evidence: "삼거리에서" },
    event: { value: "급정거", evidence: "급하게 멈췄어" },
    situation: { value: "좌회전 중 보행자 횡단", evidence: "좌회전하는데 누가 무단 횡단" },
    weather: { value: "", evidence: null },
  },
};
