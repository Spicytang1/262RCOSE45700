import { useCallback, useEffect, useRef, useState } from "react";
import { saveReview } from "./recordingStore";
import { reviewFor } from "./recordingPresentation";
import { setRecordingNavigationGuard } from "./useRecordingRoute";
import type { RecordingEntry, RecordingReview } from "@/types/report";

type SavePhase = "waiting" | "saving" | "saved" | "error";

/** 원본은 건드리지 않고 검토 내용만 순차 저장한다. 이동 직전에는 마지막 입력까지 기다린다. */
export default function useReviewAutosave(recording: RecordingEntry, onSaved: () => void) {
  const [draft, setDraft] = useState(() => reviewFor(recording));
  const [phase, setPhase] = useState<SavePhase>("waiting");
  const latest = useRef(draft);
  const persisted = useRef(recording.review ? JSON.stringify(recording.review) : "");
  const inFlight = useRef<Promise<boolean> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mounted = useRef(false);
  const onSavedRef = useRef(onSaved);
  const supervisorId = recording.supervisorId;

  useEffect(() => { onSavedRef.current = onSaved; }, [onSaved]);

  const flush = useCallback(async (): Promise<boolean> => {
    clearTimeout(timer.current);
    if (inFlight.current) {
      if (!await inFlight.current) return false;
    }
    if (JSON.stringify(latest.current) === persisted.current) {
      if (mounted.current) setPhase("saved");
      return true;
    }
    const operation = (async () => {
      while (JSON.stringify(latest.current) !== persisted.current) {
        const snapshot = latest.current;
        if (mounted.current) setPhase("saving");
        // TODO(backend): 서버 저장 완료 응답 이후에만 persisted를 갱신한다. 통신 실패·동시 수정 충돌에도 입력과 이탈 방지를 유지한다.
        try { await saveReview(snapshot, supervisorId); }
        catch { if (mounted.current) setPhase("error"); return false; }
        persisted.current = JSON.stringify(snapshot);
      }
      if (mounted.current) { setPhase("saved"); onSavedRef.current(); }
      return true;
    })();
    inFlight.current = operation;
    try { return await operation; }
    finally { if (inFlight.current === operation) inFlight.current = null; }
  }, [supervisorId]);

  useEffect(() => {
    mounted.current = true;
    // 예시 기본값도 처음 열 때 보관하며, 기존 제목·메모·수기 항목은 보존한다.
    void Promise.resolve().then(() => { if (mounted.current) return flush(); });
    const removeGuard = setRecordingNavigationGuard(flush);
    const warn = (event: BeforeUnloadEvent) => {
      if (JSON.stringify(latest.current) === persisted.current) return;
      void flush();
      event.preventDefault(); event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
      removeGuard();
      window.removeEventListener("beforeunload", warn);
    };
  }, [flush]);

  function change(update: (current: RecordingReview) => RecordingReview) {
    const next = update(latest.current);
    latest.current = next;
    setDraft(next); setPhase("waiting");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { void flush(); }, 350);
  }

  async function leave(action: () => void) { if (await flush()) action(); }

  return { draft, phase, change, flush, leave };
}
