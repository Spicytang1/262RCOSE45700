import { useCallback, useEffect, useRef, useState } from "react";
import { getRecordings, getReviews, getSessions } from "./recordingStore";
import type { DriveSession, RecordingEntry, SupervisorId } from "@/types/report";

type Data = { owner: SupervisorId | null; recordings: RecordingEntry[]; sessions: DriveSession[]; loading: boolean; error: boolean };
const EMPTY: Data = { owner: null, recordings: [], sessions: [], loading: false, error: false };

export default function useRecordingData(supervisorId: SupervisorId | null) {
  const [data, setData] = useState<Data>(EMPTY);
  const requestId = useRef(0);
  const reload = useCallback(async (signal?: AbortSignal) => {
    const request = ++requestId.current;
    if (supervisorId === null) return;
    if (signal?.aborted) return;
    setData(previous => ({ ...previous, loading: true, error: false }));
    try {
      const [recordings, sessions, reviews] = await Promise.all([getRecordings(supervisorId), getSessions(supervisorId), getReviews()]);
      const byId = new Map(reviews.map(review => [review.id, review]));
      if (!signal?.aborted && request === requestId.current) setData(previous => {
        // 원본은 불변이다. 검토 내용 갱신으로 재생 중인 음성이 초기화되지 않게 참조를 유지한다.
        const originals = new Map((previous.owner === supervisorId ? previous.recordings : []).map(record => [record.id, record.audio]));
        return { owner: supervisorId, recordings: recordings.map(record => ({ ...record, audio: originals.get(record.id) ?? record.audio, review: byId.get(record.id) })), sessions, loading: false, error: false };
      });
    } catch {
      if (!signal?.aborted && request === requestId.current) setData(previous => ({ ...(previous.owner === supervisorId ? previous : EMPTY), owner: supervisorId, loading: false, error: true }));
    }
  }, [supervisorId]);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.resolve().then(() => reload(controller.signal));
    return () => controller.abort();
  }, [reload]);

  return { ...(data.owner === supervisorId ? data : { ...EMPTY, loading: supervisorId !== null }), reload };
}
