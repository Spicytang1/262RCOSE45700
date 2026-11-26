import type { DriveSession, PendingRecording, RecordingAnalysis, RecordingEntry, RecordingLocation, RecordingReview, StructuredFieldKey, SupervisorId } from "@/types/report";
import { FIELD_CONFIG, keyForLabel, labelForKey } from "./recordingPresentation";
import {
  createDrive, deleteIssueForever, fetchIssueAudio, finishDrive, listDrives, listIssues, listReviews, patchIssue, putReview, restoreIssue, trashIssue, uploadRecording,
  type ServerDrive, type ServerExtraction, type ServerIssue, type ServerLocation, type ServerRecordingResult, type ServerReview,
} from "./serverApi";

// 모든 기록은 서버(/api)에 저장한다. 서버가 로그인한 사람의 기록만 돌려주므로 supervisorId 로 거르지 않는다.

const FIELD_KEYS = Object.keys(FIELD_CONFIG) as StructuredFieldKey[];

function toSession(drive: ServerDrive): DriveSession {
  return { id: drive.id, supervisorId: drive.operator_id, number: drive.number, startedAt: drive.started_at, endedAt: drive.ended_at };
}

/** 서버 시각에 시간대 표시가 없으면 UTC 로 본다. */
function utc(value: string) {
  return /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`;
}

function toLocation(location: ServerLocation | null | undefined): RecordingLocation | undefined {
  if (!location) return undefined;
  const requestedAt = location.requested_at ? utc(location.requested_at) : "";
  if (location.status === "available" && location.latitude != null && location.longitude != null) {
    return {
      status: "available", requestedAt, latitude: location.latitude, longitude: location.longitude,
      accuracy: location.accuracy_m ?? 0, capturedAt: location.captured_at ? utc(location.captured_at) : requestedAt,
    };
  }
  return { status: location.status === "available" ? "unavailable" : location.status, requestedAt };
}

function toServerLocation(location: RecordingLocation | undefined): ServerLocation | undefined {
  if (!location) return undefined;
  if (location.status === "available") {
    return { status: "available", latitude: location.latitude, longitude: location.longitude, accuracy_m: location.accuracy, requested_at: location.requestedAt, captured_at: location.capturedAt };
  }
  return { status: location.status, requested_at: location.requestedAt };
}

function toAnalysis(extraction: ServerExtraction | null | undefined): RecordingAnalysis {
  const fields: RecordingAnalysis["fields"] = {};
  const needsReview: StructuredFieldKey[] = [];
  for (const key of FIELD_KEYS) {
    const classified = extraction?.[FIELD_CONFIG[key].serverField as keyof ServerExtraction] as { value?: string | null; needs_review?: boolean } | undefined;
    const label = labelForKey(key, classified?.value);
    if (label) fields[key] = label;
    if (classified?.needs_review) needsReview.push(key);
  }
  return {
    fields, needsReview,
    cause: extraction?.cause?.value ?? null,
    place: extraction?.location?.value ?? null,
    mentionedTime: extraction?.mentioned_time?.value ?? null,
    estimatedAt: extraction?.mentioned_time_resolved?.estimated_at ? utc(extraction.mentioned_time_resolved.estimated_at) : null,
  };
}

function toReview(review: ServerReview): RecordingReview {
  return {
    id: review.recording_id, title: review.title, status: review.status, note: review.note,
    fields: review.fields as RecordingReview["fields"],
    otherFields: review.other_fields.filter((key): key is StructuredFieldKey => FIELD_KEYS.includes(key as StructuredFieldKey)),
    otherFieldValues: review.other_field_values as RecordingReview["otherFieldValues"],
  };
}

function toEntry(issue: ServerIssue, review: ServerReview | undefined): RecordingEntry {
  const errors = issue.pipeline_meta?.errors ? Object.keys(issue.pipeline_meta.errors) : [];
  return {
    id: issue.recording_id,
    issueId: issue.id,
    supervisorId: issue.operator_id,
    recordedAt: utc(issue.recorded_at),
    durationSec: issue.duration_sec ?? 0,
    sessionId: issue.drive_session_id ?? undefined,
    location: toLocation(issue.location),
    startTrigger: issue.start_trigger === "intervention" ? "intervention" : issue.start_trigger === "button" ? "button" : undefined,
    transcript: issue.transcript?.corrected_text ?? "",
    analysis: toAnalysis(issue.final_extraction ?? issue.ai_extraction),
    issueStatus: issue.status,
    pipelineErrors: errors,
    cancelDecision: issue.pipeline_meta?.cancel_intent?.decision,
    trashedAt: issue.trashed_at ? utc(issue.trashed_at) : undefined,
    review: review ? toReview(review) : undefined,
  };
}

export async function getSessions(signal?: AbortSignal): Promise<DriveSession[]> {
  const drives = await listDrives(signal);
  return drives.map(toSession).sort((a, b) => b.number - a.number);
}

/** 서버가 진행 중인 운행이 있으면 그 운행을 돌려준다. 여러 기기에서 눌러도 하나만 생긴다. */
export async function startSession(): Promise<DriveSession> {
  return toSession(await createDrive());
}

/** keepalive 는 화면을 떠나는 순간에도 요청이 끝까지 가도록 한다. */
export async function endSession(id: string, keepalive = false): Promise<void> {
  await finishDrive(id, keepalive);
}

/** 정상 녹음과 휴지통 녹음, 검토 내용을 함께 읽어 화면용으로 합친다. */
export async function getRecordings(signal?: AbortSignal): Promise<RecordingEntry[]> {
  const [active, trashed, reviews] = await Promise.all([listIssues(false, signal), listIssues(true, signal), listReviews(signal)]);
  const byRecording = new Map(reviews.map(review => [review.recording_id, review]));
  return [...active, ...trashed]
    .map(issue => toEntry(issue, byRecording.get(issue.recording_id)))
    .sort((a, b) => b.recordedAt.localeCompare(a.recordedAt));
}

/** 녹음을 서버에 올린다. 서버가 받아쓰기·정리·분류까지 끝내고 응답한다. */
export async function saveRecording(recording: PendingRecording): Promise<ServerRecordingResult> {
  return uploadRecording({
    audio: recording.audio,
    recordedAt: recording.recordedAt,
    durationSec: recording.durationSec,
    driveSessionId: recording.sessionId,
    startTrigger: recording.startTrigger,
    location: toServerLocation(recording.location),
  });
}

/**
 * 검토 내용을 저장하고, 정리 항목은 이슈의 최종 값에도 반영한다.
 * 검토 완료로 바꾸면 이슈를 확정(confirm)한다. 원본 음성과 AI 결과는 서버가 따로 보존한다.
 */
export async function saveReview(recording: RecordingEntry, review: RecordingReview): Promise<void> {
  if (recording.trashedAt) return;
  const status = review.status === "trashed" ? "new" : review.status;
  await putReview(recording.id, {
    title: review.title, status, note: review.note,
    fields: Object.fromEntries(Object.entries(review.fields).filter(([, value]) => typeof value === "string")) as Record<string, string>,
    other_fields: review.otherFields ?? [],
    other_field_values: Object.fromEntries(Object.entries(review.otherFieldValues ?? {}).filter(([, value]) => typeof value === "string")) as Record<string, string>,
  });
  const patch: Record<string, unknown> = {};
  // 사람이 AI 값과 다르게 고친 항목만 보낸다. 그대로 둔 항목까지 보내면 AI 정확도 비교가 흐려진다.
  for (const key of FIELD_KEYS) {
    if (review.fields[key] === recording.analysis.fields[key]) continue;
    const serverKey = keyForLabel(key, review.fields[key]);
    if (serverKey) patch[FIELD_CONFIG[key].serverField] = serverKey;
  }
  const confirm = status === "reviewed" && recording.issueStatus !== "confirmed";
  if (Object.keys(patch).length || confirm) await patchIssue(recording.issueId, { ...patch, confirm });
}

export async function trashRecording(recording: RecordingEntry) { await trashIssue(recording.issueId); }
export async function restoreRecording(recording: RecordingEntry) { await restoreIssue(recording.issueId); }
export async function deleteRecordingForever(recording: RecordingEntry) { await deleteIssueForever(recording.issueId); }
export function loadRecordingAudio(recording: RecordingEntry, signal?: AbortSignal) { return fetchIssueAudio(recording.issueId, signal); }

/** 서버 응답을 보고 녹음이 어떻게 처리됐는지 안내 문구를 만든다. */
export function uploadOutcome(result: ServerRecordingResult): "trashed" | "review" | "error" | "ok" {
  const cancel = result.pipeline_meta?.cancel_intent;
  if (cancel?.trashed) return "trashed";
  if (cancel?.decision === "review") return "review";
  if (result.status === "error") return "error";
  return "ok";
}

export type { SupervisorId };
