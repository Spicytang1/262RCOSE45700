import type { DriveSession, RecordingEntry, RecordingStatus } from "@/types/report";
import { DEMO_ADDRESS, DEMO_TRANSCRIPT, recordingSummary, recordingTitle } from "./recordingPresentation";

export type ListOptions = { scope: "all" | "session"; query: string; sort: "latest" | "oldest"; status: "all" | RecordingStatus; limit: number };
export const INITIAL_LIST_OPTIONS: ListOptions = { scope: "session", query: "", sort: "latest", status: "all", limit: 30 };

export function filteredRecordings(recordings: RecordingEntry[], session: DriveSession | undefined, options: ListOptions) {
  const query = options.query.trim().toLocaleLowerCase("ko-KR");
  return recordings.filter(record =>
    (options.scope === "all" || (!!session && record.sessionId === session.id)) &&
    (options.status === "all" || (record.review?.status ?? "new") === options.status) &&
    // TODO(backend): 서버 검색에도 제목·메모·네 정리 항목·녹음별 주소·전사를 포함한다. 주소와 전사는 현재 공통 예시다.
    (!query || `${recordingTitle(record)} ${record.review?.note ?? ""} ${recordingSummary(record)} ${DEMO_ADDRESS} ${DEMO_TRANSCRIPT}`.toLocaleLowerCase("ko-KR").includes(query)),
  ).sort((a, b) => options.sort === "latest" ? b.recordedAt.localeCompare(a.recordedAt) : a.recordedAt.localeCompare(b.recordedAt));
}
