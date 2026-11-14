import type { DriveSession, RecordingEntry, RecordingStatus } from "@/types/report";
import { recordingTitle } from "./recordingPresentation";

export type ListOptions = { scope: "all" | "session"; query: string; sort: "latest" | "oldest"; status: "all" | RecordingStatus; limit: number };
export const INITIAL_LIST_OPTIONS: ListOptions = { scope: "session", query: "", sort: "latest", status: "all", limit: 30 };

export function filteredRecordings(recordings: RecordingEntry[], session: DriveSession | undefined, options: ListOptions) {
  const query = options.query.trim().toLocaleLowerCase("ko-KR");
  return recordings.filter(record =>
    (options.scope === "all" || (!!session && record.sessionId === session.id)) &&
    (options.status === "all" || (record.review?.status ?? "new") === options.status) &&
    (!query || `${recordingTitle(record)} ${record.review?.note ?? ""}`.toLocaleLowerCase("ko-KR").includes(query)),
  ).sort((a, b) => options.sort === "latest" ? b.recordedAt.localeCompare(a.recordedAt) : a.recordedAt.localeCompare(b.recordedAt));
}
