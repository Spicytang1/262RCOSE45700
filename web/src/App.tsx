import { useEffect, useRef, useState } from "react";
import Login from "@/screens/Login/Login";
import Standby from "@/screens/Standby/Standby";
import Record from "@/screens/Record/Record";
import Review from "@/screens/Review/Review";
import Button from "@/components/Button";
import { countRecordings, saveRecording } from "@/lib/recordingStore";
import type { AudioClip, StoredRecording, SupervisorId } from "@/types/report";

type Screen = "login" | "standby" | "record" | "addRecord" | "review";

/** 로그인 → 대기 → 녹음 → 보관 → 대기. 기존 검토 흐름은 보존한다. */
export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [supervisorId, setSupervisorId] = useState<SupervisorId | null>(null);
  const [recordingCount, setRecordingCount] = useState<number | null>(null);
  const [countError, setCountError] = useState(false);
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState<StoredRecording | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const savingRef = useRef(false);
  const startedAt = useRef("");
  const [audioClips, setAudioClips] = useState<AudioClip[]>([]);

  useEffect(() => {
    if (supervisorId === null) return;
    let active = true;
    countRecordings(supervisorId).then(
      (count) => { if (active) setRecordingCount(count); },
      () => { if (active) setCountError(true); },
    );
    return () => { active = false; };
  }, [supervisorId]);

  useEffect(() => {
    if (!pending) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [pending]);

  function clearClips() {
    audioClips.forEach((c) => URL.revokeObjectURL(c.url));
    setAudioClips([]);
  }

  function handleFinish(blob: Blob, durationSec: number) {
    if (supervisorId === null) return;
    const recording: StoredRecording = {
      id: crypto.randomUUID(), supervisorId, audio: blob,
      recordedAt: startedAt.current || new Date().toISOString(), durationSec,
    };
    setPending(recording);
    void commitRecording(recording);
  }

  async function commitRecording(recording: StoredRecording) {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError(false);
    try {
      if (!recording.audio.size) throw new Error("빈 녹음");
      await saveRecording(recording);
      setPending(null);
      setNotice("녹음을 보관했어요. 주행 감독에 집중해 주세요.");
      setScreen("standby");
      try {
        setRecordingCount(await countRecordings(recording.supervisorId));
        setCountError(false);
      } catch {
        setCountError(true);
      }
    } catch {
      setSaveError(true);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  function handleAddFinish(blob: Blob, durationSec: number) {
    // 추가 녹음을 재생용 URL 배열에 덧붙이고 기록 확인 화면으로 전환
    console.log("추가녹음 형식:", blob.type, "크기:", blob.size);
    setAudioClips((prev) => [
      ...prev,
      { url: URL.createObjectURL(blob), label: `추가 녹음 ${prev.length}`, durationSec },
    ]);
    setScreen("review");
  }

  function handleSave() {
    //현재 녹음본 저장 후 대기 화면으로 돌아가기
    setScreen("standby");
  }

  function handleDeleteAndBack() {
    clearClips();
    setScreen("standby");
  }

  if (pending) {
    return (
      <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] flex-col justify-center bg-white px-6 py-8 leading-[1.8]">
        <h1 className="text-[24px] font-extrabold tracking-tight">{saveError ? "녹음을 아직 보관하지 못했어요" : "녹음을 보관하고 있어요"}</h1>
        <p role={saveError ? "alert" : "status"} className="mt-4 text-[15px] text-ink-sub">
          {saveError ? "이 화면에서 녹음을 유지하고 있어요. 기기의 저장 공간이나 브라우저의 저장 허용 여부를 확인한 뒤 다시 시도해 주세요. 화면을 닫거나 새로고침하면 이 녹음은 사라질 수 있어요." : "완료되면 자동으로 대기 화면으로 돌아가요. 잠시만 기다려 주세요."}
        </p>
        {saveError && <Button autoFocus onClick={() => void commitRecording(pending)} disabled={saving} className="mt-6 focus-visible:outline-2 focus-visible:outline-offset-4">보관 다시 시도</Button>}
      </main>
    );
  }

  if (screen === "login" || supervisorId === null) {
    return <Login onLogin={(id) => { setRecordingCount(null); setCountError(false); setSupervisorId(id); setNotice(""); setScreen("standby"); }} />;
  }

  if (screen === "record") {
    return <Record onFinish={handleFinish} onCancel={() => setScreen("standby")} />;
  }

  // 기본 흐름에서 미사용. 기존 화면 및 연결은 후속 검토 기능을 위해 보존.
  if (screen === "addRecord") {
    return <Record onFinish={handleAddFinish} onCancel={() => setScreen("review")} />;
  }

  if (screen === "review") {
    return (
      <Review
        audioClips={audioClips}
        onBack={handleDeleteAndBack}
        onAdd={() => setScreen("addRecord")}
        onSave={handleSave}
      />
    );
  }

  return <Standby
    supervisorId={supervisorId}
    recordingCount={recordingCount}
    countError={countError}
    notice={notice}
    onStart={() => { startedAt.current = new Date().toISOString(); setNotice(""); setScreen("record"); }}
    onChangeSupervisor={() => { clearClips(); setSupervisorId(null); setNotice(""); setScreen("login"); }}
  />;
}
