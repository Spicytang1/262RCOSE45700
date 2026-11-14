import { useEffect, useRef, useState } from "react";
import Login from "@/screens/Login/Login";
import Standby from "@/screens/Standby/Standby";
import Record from "@/screens/Record/Record";
import Review from "@/screens/Review/Review";
import Button from "@/components/Button";
import { endSession, saveRecording, startSession } from "@/lib/recordingStore";
import useRecordingData from "@/lib/useRecordingData";
import useRecordingRoute, { navigateRecordings, navigateStandby } from "@/lib/useRecordingRoute";
import RecordingList from "@/screens/Recordings/RecordingList";
import { filteredRecordings, INITIAL_LIST_OPTIONS, type ListOptions } from "@/lib/recordingList";
import RecordingDetail from "@/screens/Recordings/RecordingDetail";
import { RecordingFrame, RecordingHeader } from "@/screens/Recordings/RecordingChrome";
import type { AudioClip, StoredRecording, SupervisorId } from "@/types/report";

type Screen = "login" | "standby" | "record" | "addRecord" | "review";

/** 로그인 → 대기 → 녹음 → 보관 → 대기. 기존 검토 흐름은 보존한다. */
export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [supervisorId, setSupervisorId] = useState<SupervisorId | null>(null);
  const data = useRecordingData(supervisorId);
  const route = useRecordingRoute();
  const [listOptions, setListOptions] = useState<ListOptions>(INITIAL_LIST_OPTIONS);
  const [sessionAction, setSessionAction] = useState<"start" | "end" | null>(null);
  const actionLock = useRef(false);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState<StoredRecording | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const savingRef = useRef(false);
  const startedAt = useRef("");
  const [audioClips, setAudioClips] = useState<AudioClip[]>([]);

  const currentSession = data.sessions.find(session => !session.endedAt) ?? data.sessions[0];
  const activeSession = currentSession && !currentSession.endedAt ? currentSession : undefined;
  const recordingCount = currentSession ? data.recordings.filter(record => record.sessionId === currentSession.id).length : 0;

  async function changeSession(action: "start" | "end", logout = false) {
    if (supervisorId === null || actionLock.current) return;
    actionLock.current = true;
    setSessionAction(action); setActionError(""); setNotice("");
    try {
      if (action === "start") await startSession(supervisorId);
      else if (activeSession) await endSession(activeSession.id, supervisorId);
      await data.reload();
      if (logout) logoutSupervisor();
      else setNotice(action === "start" ? "운행을 시작했어요. 상황이 안정된 후 녹음해 주세요." : "운행을 종료했어요. 녹음 목록에서 기록을 확인해 주세요.");
    } catch { setActionError(`운행을 ${action === "start" ? "시작" : "종료"}하지 못했어요. 다시 시도해 주세요.`); }
    finally { actionLock.current = false; setSessionAction(null); }
  }

  function logoutSupervisor() {
    clearClips(); setSupervisorId(null); setNotice(""); setActionError(""); setScreen("login");
    setListOptions(INITIAL_LIST_OPTIONS); navigateStandby();
  }

  function changeSupervisor() {
    if (actionLock.current) return;
    if (activeSession) {
      if (window.confirm("진행 중인 운행을 종료하고 감독관을 변경할까요?")) void changeSession("end", true);
    } else logoutSupervisor();
  }

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
    if (supervisorId === null || !activeSession) return;
    const recording: StoredRecording = {
      id: crypto.randomUUID(), supervisorId, audio: blob,
      recordedAt: startedAt.current || new Date().toISOString(), durationSec,
      sessionId: activeSession.id,
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
      await data.reload();
      setPending(null);
      setNotice("녹음을 보관했어요. 주행 감독에 집중해 주세요.");
      setScreen("standby");
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
    return <Login onLogin={(id) => { setSupervisorId(id); setNotice(""); setActionError(""); setScreen("standby"); }} />;
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

  if (route.page === "list") {
    return <RecordingList supervisorId={supervisorId} recordings={data.recordings} sessions={data.sessions} currentSession={currentSession} options={listOptions} onOptions={setListOptions} onOpen={navigateRecordings} onBack={navigateStandby} loading={data.loading} error={data.error} onRetry={() => void data.reload()} />;
  }

  if (route.page === "detail") {
    const record = data.recordings.find(item => item.id === route.id);
    if (data.error || (!record && data.loading)) return <RecordingFrame><RecordingHeader title="녹음 상세" backLabel="목록" onBack={() => navigateRecordings()} /><div className="p-5"><p role={data.error ? "alert" : "status"}>{data.error ? "녹음을 읽지 못했어요. 다시 시도해 주세요." : "녹음을 불러오는 중이에요…"}</p>{data.error && <Button onClick={() => void data.reload()} className="mt-4">다시 불러오기</Button>}</div></RecordingFrame>;
    if (!record) return <RecordingFrame><RecordingHeader title="녹음을 찾을 수 없어요" backLabel="목록" onBack={() => navigateRecordings()} /><p className="p-5 text-[14px] text-ink-sub">현재 감독관의 보관 목록에 없는 녹음이에요.</p></RecordingFrame>;
    const filtered = filteredRecordings(data.recordings, currentSession, listOptions);
    const siblings = filtered.some(item => item.id === record.id) ? filtered : data.recordings;
    const index = siblings.findIndex(item => item.id === record.id);
    return <RecordingDetail key={record.id} recording={record} session={data.sessions.find(session => session.id === record.sessionId)} position={index + 1} total={siblings.length} previousId={siblings[index - 1]?.id} nextId={siblings[index + 1]?.id} onOpen={navigateRecordings} onBack={() => navigateRecordings()} onSaved={() => void data.reload()} />;
  }

  return <Standby
    supervisorId={supervisorId}
    recordingCount={recordingCount}
    session={currentSession}
    loadState={data.loading ? "loading" : data.error ? "error" : "ready"}
    actionState={sessionAction ? "busy" : "idle"}
    actionError={actionError}
    notice={notice}
    onStart={() => { if (!activeSession || sessionAction || data.loading || data.error) return; startedAt.current = new Date().toISOString(); setNotice(""); navigateStandby(); setScreen("record"); }}
    onStartSession={() => void changeSession("start")}
    onEndSession={() => { if (window.confirm("이번 운행을 종료할까요? 보관한 녹음은 그대로 남아요.")) void changeSession("end"); }}
    onOpenRecordings={() => { setListOptions(INITIAL_LIST_OPTIONS); navigateRecordings(); }}
    onRetry={() => void data.reload()}
    onChangeSupervisor={changeSupervisor}
  />;
}
