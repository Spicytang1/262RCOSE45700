import type { DriveSession, RecordingEntry, RecordingStatus } from "@/types/report";
import { locationText, recordingStatus, recordingSummary, recordingTitle } from "./recordingPresentation";

export type ListOptions = { scope: "all" | "session"; query: string; sort: "latest" | "oldest"; status: "all" | RecordingStatus; limit: number };
export const INITIAL_LIST_OPTIONS: ListOptions = { scope: "session", query: "", sort: "latest", status: "all", limit: 30 };

/** 휴지통 녹음은 "휴지통" 상태를 골랐을 때만 보여 준다. */
export function filteredRecordings(recordings: RecordingEntry[], session: DriveSession | undefined, options: ListOptions) {
  const query = options.query.trim().toLocaleLowerCase("ko-KR");
  return recordings.filter(record => {
    const status = recordingStatus(record);
    return (options.scope === "all" || (!!session && record.sessionId === session.id)) &&
      (options.status === "all" ? status !== "trashed" : status === options.status) &&
      (!query || `${recordingTitle(record)} ${record.review?.note ?? ""} ${recordingSummary(record)} ${locationText(record)} ${record.transcript}`.toLocaleLowerCase("ko-KR").includes(query));
  }).sort((a, b) => options.sort === "latest" ? b.recordedAt.localeCompare(a.recordedAt) : a.recordedAt.localeCompare(b.recordedAt));
}
