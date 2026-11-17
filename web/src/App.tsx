import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import Login from "@/screens/Login/Login";
import Standby from "@/screens/Standby/Standby";
import Record, { type FinishReason } from "@/screens/Record/Record";
// import Review from "@/screens/Review/Review";
import Button from "@/components/Button";
import ConfirmSheet from "@/components/ConfirmSheet";
import StateView from "@/components/StateView";
import { endSession, getSessions, saveRecording, startSession } from "@/lib/recordingStore";
import useRecordingData from "@/lib/useRecordingData";
import useRecordingRoute, { navigateRecordings, navigateStandby } from "@/lib/useRecordingRoute";
import RecordingList from "@/screens/Recordings/RecordingList";
import { filteredRecordings, INITIAL_LIST_OPTIONS, type ListOptions } from "@/lib/recordingList";
import RecordingDetail from "@/screens/Recordings/RecordingDetail";
import { RecordingFrame, RecordingHeader } from "@/screens/Recordings/RecordingChrome";
import type { AudioClip, RecordingLocation, RecordingStartTrigger, StoredRecording, Supervisor } from "@/types/report";
import { captureRecordingLocation } from "@/lib/recordingLocation";
import { resolveSupervisor, useSessionProfiles } from "@/lib/sessionProfiles";
import Settings from "@/screens/Settings/Settings";
import { requestDrivePermissions, type DrivePermissions } from "@/lib/drivePermissions";

type Screen = "login" | "standby" | "record" | "addRecord" | "review";

/** 로그인 → 대기 → 녹음 → 보관 → 대기. 기존 검토 흐름은 보존한다. */
export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  // TODO(backend): 선택한 감독관을 메모리에만 유지한다. 서버 로그인 세션과 현재 사용자 조회를 연결하고 만료 시 로그인으로 전환한다.
  const [supervisor, setSupervisor] = useState<Supervisor | null>(null);
  const profiles = useSessionProfiles();
  const profile = supervisor ? resolveSupervisor(supervisor, profiles) : null;
  const supervisorId = supervisor?.id ?? null;
  const data = useRecordingData(supervisorId);
  const route = useRecordingRoute();
  const [listOptions, setListOptions] = useState<ListOptions>(INITIAL_LIST_OPTIONS);
  const [sessionAction, setSessionAction] = useState<"start" | "end" | null>(null);
  const actionLock = useRef(false);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmEnd, setConfirmEnd] = useState<"end" | "switch" | null>(null);
  const [pending, setPending] = useState<StoredRecording | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const savingRef = useRef(false);
  const startedAt = useRef("");
  // 녹음이 끝난 이유(수동/무음 자동 종료). 보관 재시도에서도 안내 문구를 유지하기 위해 ref에 둔다.
  const finishReasonRef = useRef<FinishReason>("manual");
  // 녹음 시작 방식. 현재는 직접 녹음 버튼만 있다. 차량 수동 개입 자동 시작은 연동하지 않는다.
  const startTriggerRef = useRef<RecordingStartTrigger>("button");
  const locationRequest = useRef<{ controller: AbortController; result: Promise<RecordingLocation> } | null>(null);
  const [audioClips, setAudioClips] = useState<AudioClip[]>([]);
  const [drivePermissions, setDrivePermissions] = useState<DrivePermissions | null>(null);
  const permissionRequest = useRef<AbortController | null>(null);

  useEffect(() => () => { locationRequest.current?.controller.abort(); permissionRequest.current?.abort(); }, []);

  function checkDrivePermissions() {
    permissionRequest.current?.abort();
    const controller = new AbortController();
    permissionRequest.current = controller;
    setDrivePermissions({ microphone: "checking", location: "checking" });
    void requestDrivePermissions(controller.signal, (kind, status) => {
      setDrivePermissions(current => !controller.signal.aborted && current ? { ...current, [kind]: status } : current);
    });
  }

  function clearDrivePermissions() {
    permissionRequest.current?.abort();
    permissionRequest.current = null;
    setDrivePermissions(null);
  }

  function cancelRecording() {
    locationRequest.current?.controller.abort();
    locationRequest.current = null;
    setScreen("standby");
  }

  function beginRecording() {
    if (!activeSession || sessionAction || data.loading || data.error || drivePermissions?.microphone === "checking" || drivePermissions?.location === "checking") return;
    locationRequest.current?.controller.abort();
    const controller = new AbortController();
    startedAt.current = new Date().toISOString();
    startTriggerRef.current = "button";
    locationRequest.current = { controller, result: captureRecordingLocation(controller.signal) };
    setNotice(""); navigateStandby(); setScreen("record");
  }

  const currentSession = data.sessions.find(session => !session.endedAt) ?? data.sessions[0];
  const activeSession = currentSession && !currentSession.endedAt ? currentSession : undefined;
  const recordingCount = currentSession ? data.recordings.filter(record => record.sessionId === currentSession.id).length : 0;

  async function changeSession(action: "start" | "end", logout = false) {
    if (supervisorId === null || actionLock.current) return;
    actionLock.current = true;
    setSessionAction(action); setActionError(""); setNotice("");
    try {
      if (action === "start") { checkDrivePermissions(); await startSession(supervisorId); }
      else if (activeSession) { await endSession(activeSession.id, supervisorId); clearDrivePermissions(); }
      await data.reload();
      if (logout) logoutSupervisor();
      else setNotice(action === "start" ? "운행을 시작했어요. 상황이 안정된 후 녹음해 주세요." : "운행을 종료했어요. 녹음 목록에서 기록을 확인해 주세요.");
    } catch { if (action === "start") clearDrivePermissions(); setActionError(`운행을 ${action === "start" ? "시작" : "종료"}하지 못했어요. 다시 시도해 주세요.`); }
    finally { actionLock.current = false; setSessionAction(null); }
  }

  function logoutSupervisor() {
    // TODO(backend): 화면 상태 초기화 외에 서버 로그아웃으로 세션도 무효화한다. 감독관 전환 시에도 같은 처리가 필요하다.
    clearDrivePermissions();
    clearClips(); setSupervisor(null); setNotice(""); setActionError(""); setScreen("login");
    setListOptions(INITIAL_LIST_OPTIONS); navigateStandby();
  }

  async function loginSupervisor(selected: Supervisor, signal: AbortSignal) {
    // 종료 순간에는 브라우저가 비동기 보관을 중단할 수 있어, 로그인 완료 전에 남은 이전 운행도 종료한다.
    // TODO(backend): 서버 로그인 시 이전 운행 정리와 세션 소유권을 확인한다. 실제 이탈 시각 확정은 서버 생존 신호·만료 정책이 필요하다.
    const sessions = await getSessions(selected.id);
    for (const session of sessions) {
      if (signal.aborted) return;
      if (!session.endedAt) await endSession(session.id, selected.id);
    }
    if (signal.aborted) return;
    clearDrivePermissions();
    setSupervisor(selected); setNotice(""); setActionError(""); setScreen("standby");
  }

  // 해시 주소를 사용하는 목록·상세·설정 이동이나 탭 전환은 종료가 아니다.
  // beforeunload는 사용자가 이동을 취소할 수도 있으므로 실제 이탈인 pagehide에서만 종료를 시도한다.
  // 매 렌더마다 최신 회차·감독관 변경 처리로 교체하고, effect 정리 자체에서는 운행을 종료하지 않는다.
  useEffect(() => {
    if (!activeSession || supervisorId === null) return;
    const onPageHide = () => { void endSession(activeSession.id, supervisorId).catch(() => { /* 다음 로그인에서 종료를 재시도한다. */ }); };
    const onPageShow = (event: PageTransitionEvent) => { if (event.persisted) logoutSupervisor(); };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
    };
  });

  function changeSupervisor() {
    if (actionLock.current) return;
    if (activeSession) {
      setConfirmEnd("switch");
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

  function handleFinish(blob: Blob, durationSec: number, reason: FinishReason) {
    if (supervisorId === null || !activeSession) return;
    const recording: StoredRecording = {
      id: crypto.randomUUID(), supervisorId, audio: blob,
      recordedAt: startedAt.current || new Date().toISOString(), durationSec,
      sessionId: activeSession.id,
      startTrigger: startTriggerRef.current,
    };
    finishReasonRef.current = reason;
    setPending(recording);
    void commitRecording(recording);
  }

  async function commitRecording(recording: StoredRecording) {
    // TODO(backend): 실제 업로드 성공 후에만 보관 완료를 표시한다. 현재 saveRecording은 이 브라우저 안에만 저장한다.
    // 브라우저 마이크·위치는 실제 측정값이며 유지하고, 전사·구조화 요청은 서버에 보관된 녹음 ID와 연결한다.
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError(false);
    try {
      if (!recording.audio.size) throw new Error("빈 녹음");
      const location = recording.location ?? await locationRequest.current?.result;
      const complete = { ...recording, ...(location ? { location } : {}) };
      // 보관 실패 시 재시도해도 처음 받은 위치와 원본을 그대로 유지한다.
      setPending(complete);
      await saveRecording(complete);
      await data.reload();
      locationRequest.current = null;
      setPending(null);
      setNotice(finishReasonRef.current === "silence"
        ? "무음이 4초 이어져 녹음을 자동으로 끝냈어요. 녹음은 보관했어요."
        : "녹음을 보관했어요. 주행 감독에 집중해 주세요.");
      setScreen("standby");
    } catch {
      setSaveError(true);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }


  //추가녹음 화면용 함수 (추가녹음 화면 현재 미사용)
  /*
  function handleAddFinish(blob: Blob, durationSec: number) {

    console.log("추가녹음 형식:", blob.type, "크기:", blob.size);
    setAudioClips((prev) => [
      ...prev,
      { url: URL.createObjectURL(blob), label: `추가 녹음 ${prev.length}`, durationSec },
    ]);
    setScreen("review");
  }
    */

  //녹음 결과 화면용 함수 (녹음 결과 화면 현재 미사용)
  /*
  function handleSave() {
     setScreen("standby");
  }

  function handleDeleteAndBack() {
    clearClips();
    setScreen("standby");
  }

  */

  if (pending) {
    return (
      <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] flex-col justify-center bg-white px-6 py-8 leading-[1.8]">
        {saveError
          ? <span className="mb-5 flex size-14 items-center justify-center rounded-full bg-warning-soft text-warning-ink" aria-hidden="true"><AlertCircle className="size-7" /></span>
          : <span aria-hidden="true" className="mb-5 size-12 animate-spin rounded-full border-[4px] border-line border-t-kakao-press motion-reduce:animate-none" />}
        <h1 className="text-[24px] font-extrabold tracking-tight">{saveError ? "녹음을 아직 보관하지 못했어요" : "녹음을 보관하고 있어요"}</h1>
        <p role={saveError ? "alert" : "status"} className="mt-4 text-[15px] text-ink-sub">
          {saveError ? "이 화면에서 녹음을 유지하고 있어요. 기기의 저장 공간이나 브라우저의 저장 허용 여부를 확인한 뒤 다시 시도해 주세요. 화면을 닫거나 새로고침하면 이 녹음은 사라질 수 있어요." : "녹음과 시작 시 요청한 위치를 보관하고 있어요. 위치 확인은 최대 10초 기다리며, 확인하지 못해도 음성은 보관해요. 완료되면 대기로 돌아가요."}
        </p>
        {saveError && <Button autoFocus onClick={() => void commitRecording(pending)} disabled={saving} className="mt-6 focus-visible:outline-2 focus-visible:outline-offset-4">보관 다시 시도</Button>}
      </main>
    );
  }

  if (screen === "login" || supervisorId === null || !profile) {
    return <Login onLogin={loginSupervisor} />;
  }

  if (screen === "record") {
    return <Record onFinish={handleFinish} onCancel={cancelRecording} />;
  }

  //추가녹음 화면 (미사용)
  /*
  if (screen === "addRecord") {
    return <Record onFinish={handleAddFinish} onCancel={() => setScreen("review")} />;
  }
    */


  //녹음 결과 화면 (미사용)
  /*
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
    */

  if (route.page === "settings") return <Settings profile={profile} onBack={navigateStandby} />;

  if (route.page === "list") {
    return <RecordingList supervisorName={profile.name} recordings={data.recordings} sessions={data.sessions} currentSession={currentSession} options={listOptions} onOptions={setListOptions} onOpen={navigateRecordings} onBack={navigateStandby} loading={data.loading} error={data.error} onRetry={() => void data.reload()} />;
  }

  if (route.page === "detail") {
    const record = data.recordings.find(item => item.id === route.id);
    if (data.error || (!record && data.loading)) return <RecordingFrame><RecordingHeader title="녹음 상세" backLabel="목록" onBack={() => navigateRecordings()} /><div className="p-5">{data.error ? <StateView kind="error" message="녹음을 읽지 못했어요. 다시 시도해 주세요." onRetry={() => void data.reload()} /> : <StateView kind="loading" message="녹음을 불러오는 중이에요…" />}</div></RecordingFrame>;
    if (!record) return <RecordingFrame><RecordingHeader title="녹음 상세" backLabel="목록" onBack={() => navigateRecordings()} /><div className="p-5"><StateView kind="empty" title="녹음을 찾을 수 없어요" message="현재 감독관의 보관 목록에 없는 녹음이에요." /></div></RecordingFrame>;
    const filtered = filteredRecordings(data.recordings, currentSession, listOptions);
    const siblings = filtered.some(item => item.id === record.id) ? filtered : data.recordings;
    const index = siblings.findIndex(item => item.id === record.id);
    return <RecordingDetail key={record.id} supervisorName={profile.name} recording={record} session={data.sessions.find(session => session.id === record.sessionId)} position={index + 1} total={siblings.length} previousId={siblings[index - 1]?.id} nextId={siblings[index + 1]?.id} onOpen={navigateRecordings} onBack={() => navigateRecordings()} onSaved={() => void data.reload()} />;
  }

  return <>
  <Standby
    permissions={drivePermissions}
    profile={profile}
    recordingCount={recordingCount}
    session={currentSession}
    loadState={data.loading ? "loading" : data.error ? "error" : "ready"}
    actionState={sessionAction ? "busy" : "idle"}
    actionError={actionError}
    notice={notice}
    onStart={beginRecording}
    onStartSession={() => void changeSession("start")}
    onEndSession={() => setConfirmEnd("end")}
    onOpenRecordings={() => { setListOptions(INITIAL_LIST_OPTIONS); navigateRecordings(); }}
    onRetry={() => void data.reload()}
    onChangeSupervisor={changeSupervisor}
  />
  {confirmEnd && <ConfirmSheet title={confirmEnd === "switch" ? "운행을 종료하고 감독관을 바꿀까요?" : "이번 운행을 종료할까요?"} message="보관한 녹음은 그대로 남아요. 종료한 뒤에는 새 운행을 시작해야 녹음할 수 있어요." confirmLabel={confirmEnd === "switch" ? "종료하고 변경" : "운행 종료"} onCancel={() => setConfirmEnd(null)} onConfirm={() => { const mode = confirmEnd; setConfirmEnd(null); void (mode === "switch" ? changeSession("end", true) : changeSession("end")); }} />}
  </>;
}
