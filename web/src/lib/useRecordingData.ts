import { useCallback, useEffect, useRef, useState } from "react";
import { getRecordings, getSessions } from "./recordingStore";
import type { DriveSession, RecordingEntry, SupervisorId } from "@/types/report";

type Data = { owner: SupervisorId | null; recordings: RecordingEntry[]; sessions: DriveSession[]; loading: boolean; error: boolean };
const EMPTY: Data = { owner: null, recordings: [], sessions: [], loading: false, error: false };

/** 로그인한 감독관의 녹음·운행 회차를 서버에서 읽는다. 검색·필터는 화면에서 한다. */
export default function useRecordingData(supervisorId: SupervisorId | null) {
  const [data, setData] = useState<Data>(EMPTY);
  const requestId = useRef(0);
  const reload = useCallback(async (signal?: AbortSignal) => {
    const request = ++requestId.current;
    if (supervisorId === null) return;
    if (signal?.aborted) return;
    setData(previous => ({ ...previous, loading: previous.owner !== supervisorId || previous.recordings.length === 0, error: false }));
    try {
      const [recordings, sessions] = await Promise.all([getRecordings(signal), getSessions(signal)]);
      if (!signal?.aborted && request === requestId.current) setData({ owner: supervisorId, recordings, sessions, loading: false, error: false });
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
