import { apiFetch, apiJson, ApiError } from "./api";

/** 서버 응답 형식 (backend/contracts, /openapi.json 기준) */
export type ServerDrive = { id: string; operator_id: string; number: number; started_at: string; ended_at: string | null };

export type Evidenced = { value: string | null; evidence?: string | null; needs_review?: boolean; review_reason?: string | null };
export type Classified = { value: string | null; probabilities?: Record<string, number>; confidence?: number | null; needs_review?: boolean };
export type ServerExtraction = {
  cause: Evidenced;
  location: Evidenced;
  mentioned_time: Evidenced;
  event_type: Classified;
  severity: Classified;
  road_type?: Classified;
  ego_action_before?: Classified;
  target_type?: Classified;
  ego_reaction?: Classified;
  mentioned_time_resolved?: { expression: string; estimated_at: string; window_start: string; window_end: string } | null;
};

export type CancelIntent = { decision: "trash" | "review" | "keep" | "skipped"; probability: number | null; trashed: boolean; error?: string };
export type ServerPipelineMeta = {
  stt_provider?: string;
  extractor_model?: string;
  errors?: Record<string, string> | null;
  cancel_intent?: CancelIntent;
  speakers?: { count: number; driver: string | null };
};

export type ServerLocation = {
  status: "available" | "denied" | "timeout" | "unavailable" | "unsupported" | "insecure";
  latitude?: number | null;
  longitude?: number | null;
  accuracy_m?: number | null;
  requested_at?: string | null;
  captured_at?: string | null;
};

export type ServerIssue = {
  id: string;
  recording_id: string;
  recorded_at: string;
  operator_id: string;
  status: "draft" | "confirmed" | "error";
  ai_extraction: ServerExtraction;
  final_extraction: ServerExtraction | null;
  confirmed_at: string | null;
  pipeline_meta: ServerPipelineMeta;
  transcript: { raw_text: string; corrected_text: string };
  drive_session_id?: string | null;
  duration_sec?: number | null;
  start_trigger?: string | null;
  location?: ServerLocation | null;
  trashed_at?: string | null;
};

export type ServerRecordingResult = {
  recording_id: string;
  issue_id: string;
  recorded_at: string;
  status: ServerIssue["status"];
  transcript: ServerIssue["transcript"];
  extraction: ServerExtraction;
  pipeline_meta: ServerPipelineMeta;
};

export type ServerReview = {
  id: string;
  recording_id: string;
  title: string;
  status: "new" | "reviewed" | "flagged";
  note: string;
  fields: Record<string, string>;
  other_fields: string[];
  other_field_values: Record<string, string>;
  updated_at: string;
};

export type ServerReviewWrite = Omit<ServerReview, "id" | "recording_id" | "updated_at">;

export type TaxonomyOption = { key: string; label: string; description: string };
export type Taxonomy = {
  version: string;
  event_types: TaxonomyOption[];
  severity_levels: TaxonomyOption[];
  guide: { id: string; review_field: string; label: string; prompt: string; options: TaxonomyOption[] }[];
};

// 운행
export const listDrives = (signal?: AbortSignal) => apiJson<ServerDrive[]>("/api/drives", { signal }, "운행 목록을 불러오지 못했어요.");
export const createDrive = () => apiJson<ServerDrive>("/api/drives", { method: "POST" }, "운행을 시작하지 못했어요.");
export const finishDrive = (id: string, keepalive = false) => apiJson<ServerDrive>(`/api/drives/${encodeURIComponent(id)}/end`, { method: "POST", keepalive }, "운행을 종료하지 못했어요.");

// 녹음 업로드 (서버가 받아쓰기·정리·분류까지 끝낸 뒤 응답한다)
export type UploadInput = {
  audio: Blob;
  recordedAt: string;
  durationSec: number;
  driveSessionId: string;
  startTrigger: "button" | "intervention";
  location?: ServerLocation;
};

export async function uploadRecording(input: UploadInput): Promise<ServerRecordingResult> {
  const form = new FormData();
  const extension = input.audio.type.includes("mp4") ? "m4a" : input.audio.type.includes("ogg") ? "ogg" : "webm";
  form.append("audio", input.audio, `recording.${extension}`);
  form.append("recorded_at", input.recordedAt);
  form.append("duration_sec", String(input.durationSec));
  form.append("drive_session_id", input.driveSessionId);
  form.append("start_trigger", input.startTrigger);
  const location = input.location;
  if (location) {
    form.append("location_status", location.status);
    if (location.latitude != null) form.append("latitude", String(location.latitude));
    if (location.longitude != null) form.append("longitude", String(location.longitude));
    if (location.accuracy_m != null) form.append("location_accuracy_m", String(location.accuracy_m));
    if (location.requested_at) form.append("location_requested_at", location.requested_at);
    if (location.captured_at) form.append("location_captured_at", location.captured_at);
  }
  return apiJson<ServerRecordingResult>("/api/recordings", { method: "POST", body: form }, "녹음을 서버에 올리지 못했어요.");
}

// 이슈 (녹음 1건 = 이슈 1건)
export const listIssues = (trashed: boolean, signal?: AbortSignal) =>
  apiJson<ServerIssue[]>(`/api/issues?trashed=${trashed}`, { signal }, "녹음 목록을 불러오지 못했어요.");
export const getIssue = (id: string, signal?: AbortSignal) => apiJson<ServerIssue>(`/api/issues/${encodeURIComponent(id)}`, { signal }, "녹음을 불러오지 못했어요.");
export const patchIssue = (id: string, body: Record<string, unknown>) =>
  apiJson<ServerIssue>(`/api/issues/${encodeURIComponent(id)}`, { method: "PATCH", json: body }, "정리 결과를 저장하지 못했어요.");
export const trashIssue = (id: string) => apiJson<ServerIssue>(`/api/issues/${encodeURIComponent(id)}/trash`, { method: "POST" }, "휴지통에 넣지 못했어요.");
export const restoreIssue = (id: string) => apiJson<ServerIssue>(`/api/issues/${encodeURIComponent(id)}/restore`, { method: "POST" }, "휴지통에서 복구하지 못했어요.");
export const deleteIssueForever = (id: string) => apiJson<void>(`/api/issues/${encodeURIComponent(id)}`, { method: "DELETE" }, "영구 삭제하지 못했어요.");

/** 원본 음성. 인증이 필요해서 <audio src> 대신 받아서 Blob 으로 재생한다. */
export async function fetchIssueAudio(id: string, signal?: AbortSignal): Promise<Blob> {
  const response = await apiFetch(`/api/issues/${encodeURIComponent(id)}/audio`, { signal });
  if (!response.ok) throw new ApiError(response.status, "원본 음성을 불러오지 못했어요.");
  return response.blob();
}

// 검토 (화면에서 고친 제목·상태·정리 항목·메모)
export const listReviews = (signal?: AbortSignal) => apiJson<ServerReview[]>("/api/reviews", { signal }, "검토 내용을 불러오지 못했어요.");
export const putReview = (recordingId: string, body: ServerReviewWrite) =>
  apiJson<ServerReview>(`/api/reviews/${encodeURIComponent(recordingId)}`, { method: "PUT", json: body }, "검토 내용을 저장하지 못했어요.");

// 분류 보기
export const getTaxonomy = (signal?: AbortSignal) => apiJson<Taxonomy>("/api/taxonomy", { signal }, "분류 보기를 불러오지 못했어요.");
