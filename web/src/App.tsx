import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import Login from "@/screens/Login/Login";
import Standby from "@/screens/Standby/Standby";
import Record, { type FinishReason } from "@/screens/Record/Record";
import { primeSpeech, speak } from "@/lib/speak";
// import Review from "@/screens/Review/Review";
import Button from "@/components/Button";
import ConfirmSheet from "@/components/ConfirmSheet";
import StateView from "@/components/StateView";
import PageTransition from "@/components/PageTransition";
import { endSession, getSessions, saveRecording, startSession, uploadOutcome } from "@/lib/recordingStore";
import useRecordingData from "@/lib/useRecordingData";
import useRecordingRoute, { navigateRecordings, navigateStandby } from "@/lib/useRecordingRoute";
import RecordingList from "@/screens/Recordings/RecordingList";
import { filteredRecordings, INITIAL_LIST_OPTIONS, type ListOptions } from "@/lib/recordingList";
import RecordingDetail from "@/screens/Recordings/RecordingDetail";
import { RecordingFrame, RecordingHeader } from "@/screens/Recordings/RecordingChrome";
import type { AudioClip, PendingRecording, RecordingLocation, RecordingStartTrigger, Supervisor } from "@/types/report";
import { captureRecordingLocation } from "@/lib/recordingLocation";
import { resolveSupervisor, useSessionProfiles } from "@/lib/sessionProfiles";
import Settings from "@/screens/Settings/Settings";
import { requestDrivePermissions, type DrivePermissions } from "@/lib/drivePermissions";
import { logoutSession, onSessionExpired, refreshAccessToken } from "@/lib/api";

type Screen = "login" | "standby" | "record" | "addRecord" | "review";

/** 로그인 → 대기 → 녹음 → 보관 → 대기. 기존 검토 흐름은 보존한다. */
export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  // 로그인한 감독관. 새로고침하면 로그인 유지 쿠키로 다시 불러온다(booting).
  const [supervisor, setSupervisor] = useState<Supervisor | null>(null);
  const [booting, setBooting] = useState(true);
  const [loginNotice, setLoginNotice] = useState("");
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
  const [pending, setPending] = useState<PendingRecording | null>(null);
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

  // 새로고침해도 로그인을 유지한다. 서버의 로그인 유지 쿠키로 access token 을 다시 받는다.
  useEffect(() => {
    const controller = new AbortController();
    void refreshAccessToken(controller.signal).then(result => {
      if (controller.signal.aborted) return;
      if (result) { setSupervisor({ id: result.user.id, name: result.user.display_name, photoUrl: null }); setScreen("standby"); }
      setBooting(false);
    });
    return () => controller.abort();
  }, []);

  // 로그인 유지가 끊기면(재발급 실패) 로그인 화면으로 보낸다.
  useEffect(() => onSessionExpired(() => {
    clearDrivePermissions();
    setSupervisor(null); setScreen("login"); navigateStandby();
    setLoginNotice("로그인이 만료됐어요. 다시 로그인해 주세요.");
  }), []);

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
    primeSpeech(); // iOS 사파리에서 이후 자동 음성 안내가 나오도록 버튼을 누른 순간에 준비해 둔다.
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
      if (action === "start") { checkDrivePermissions(); await startSession(); }
      else if (activeSession) { await endSession(activeSession.id); clearDrivePermissions(); }
      await data.reload();
      if (logout) logoutSupervisor();
      else setNotice(action === "start" ? "운행을 시작했어요. 안전한 상황에서 녹음해 주세요." : "운행을 종료했어요.");
    } catch { if (action === "start") clearDrivePermissions(); setActionError(`운행을 ${action === "start" ? "시작" : "종료"}하지 못했어요. 다시 시도해 주세요.`); }
    finally { actionLock.current = false; setSessionAction(null); }
  }

  function logoutSupervisor() {
    void logoutSession().finally(() => {
      clearDrivePermissions();
      clearClips(); setSupervisor(null); setNotice(""); setActionError(""); setScreen("login");
      setListOptions(INITIAL_LIST_OPTIONS); navigateStandby();
    });
  }

  async function loginSupervisor(selected: Supervisor, signal: AbortSignal) {
    // 종료 순간에는 브라우저가 비동기 보관을 중단할 수 있어, 로그인 완료 전에 남은 이전 운행도 종료한다.
    const sessions = await getSessions(signal);
    for (const session of sessions) {
      if (signal.aborted) return;
      if (!session.endedAt) await endSession(session.id);
    }
    if (signal.aborted) return;
    clearDrivePermissions();
    setLoginNotice("");
    setSupervisor(selected); setNotice(""); setActionError(""); setScreen("standby");
  }

  // 해시 주소를 사용하는 목록·상세·설정 이동이나 탭 전환은 종료가 아니다.
  // beforeunload는 사용자가 이동을 취소할 수도 있으므로 실제 이탈인 pagehide에서만 종료를 시도한다.
  // 매 렌더마다 최신 회차·감독관 변경 처리로 교체하고, effect 정리 자체에서는 운행을 종료하지 않는다.
  useEffect(() => {
    if (!activeSession || supervisorId === null) return;
    const onPageHide = () => { void endSession(activeSession.id, true).catch(() => { /* 다음 로그인에서 종료를 재시도한다. */ }); };
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
    const recording: PendingRecording = {
      supervisorId, audio: blob,
      recordedAt: startedAt.current || new Date().toISOString(), durationSec,
      sessionId: activeSession.id,
      startTrigger: startTriggerRef.current,
    };
    finishReasonRef.current = reason;
    // 화면을 보지 않아도 알 수 있게, 말 없이 끝난 경우는 소리로도 알린다.
    if (reason === "nospeech") void speak("말씀이 없어서 녹음을 마쳤어요. 나중에 목록에서 채워 주세요.", "ended");
    setPending(recording);
    void commitRecording(recording);
  }

  /** 서버 업로드가 성공해야 보관 완료다. 실패하면 원본을 화면에 남겨 다시 보낼 수 있게 한다. */
  async function commitRecording(recording: PendingRecording) {
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
      const result = await saveRecording(complete);
      await data.reload();
      locationRequest.current = null;
      setPending(null);
      const ended = finishReasonRef.current === "nospeech"
        ? "말이 없어서 녹음을 마쳤어요. 이슈를 놓치지 않게 목록에 남겨 두었으니 나중에 채워 주세요."
        : finishReasonRef.current === "silence"
        ? "4초 동안 목소리가 들리지 않아 녹음을 마쳤어요."
        : finishReasonRef.current === "voice" ? "음성 종료 명령을 인식해 녹음을 마쳤어요." : "";
      const outcome = uploadOutcome(result);
      const saved = outcome === "trashed" ? "취소 요청으로 알아듣고 휴지통에 넣었어요. 목록의 휴지통에서 복구할 수 있어요."
        : outcome === "review" ? "녹음을 보관했어요. 취소 요청인지 애매해서 목록에 표시해 두었어요."
          : outcome === "error" ? "녹음은 보관했지만 자동 정리 일부가 실패했어요. 목록에서 확인해 주세요."
            : "녹음을 보관했어요.";
      setNotice([ended, saved].filter(Boolean).join(" "));
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

  const page = (key: string, depth: number, node: ReactNode, order = 0) => <PageTransition pageKey={key} depth={depth} order={order}>{node}</PageTransition>;

  if (pending) {
    return page("saving", 4, (
      <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] flex-col justify-center bg-white px-6 py-8 leading-[1.8]">
        {saveError
          ? <span className="mb-5 flex size-14 items-center justify-center rounded-full bg-warning-soft text-warning-ink" aria-hidden="true"><AlertCircle className="size-7" /></span>
          : <span aria-hidden="true" className="mb-5 size-12 animate-spin rounded-full border-[4px] border-line border-t-kakao-press motion-reduce:animate-none" />}
        <h1 className="text-[24px] font-extrabold tracking-tight">{saveError ? "녹음을 아직 보관하지 못했어요" : "녹음을 보관하고 있어요"}</h1>
        <p role={saveError ? "alert" : "status"} className="mt-4 text-[15px] text-ink-sub">
          {saveError ? "녹음은 이 화면에 그대로 남아 있어요. 인터넷 연결을 확인한 뒤 다시 시도해 주세요. 화면을 닫거나 새로고침하면 녹음이 사라질 수 있어요." : "서버에 올리고 받아쓰는 중이에요. 녹음 길이에 따라 수십 초가 걸릴 수 있어요."}
        </p>
        {saveError && <Button onClick={() => void commitRecording(pending)} disabled={saving} className="mt-6 focus-visible:outline-2 focus-visible:outline-offset-4">보관 다시 시도</Button>}
      </main>
    ));
  }

  if (booting) {
    return page("boot", 0, <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] items-center justify-center bg-ink"><span role="status" aria-label="로그인 정보를 확인하고 있어요" className="size-10 animate-spin rounded-full border-[4px] border-white/20 border-t-kakao motion-reduce:animate-none" /></main>);
  }

  if (screen === "login" || supervisorId === null || !profile) {
    return page("login", 0, <Login onLogin={loginSupervisor} notice={loginNotice} />);
  }

  if (screen === "record") {
    return page("record", 2, <Record onFinish={handleFinish} onCancel={cancelRecording} />);
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

  if (route.page === "settings") return page("settings", 2, <Settings profile={profile} onBack={navigateStandby} onNameChange={name => setSupervisor(current => current ? { ...current, name } : current)} onLoggedOut={logoutSupervisor} />);

  if (route.page === "list") {
    return page("list", 2, <RecordingList supervisorName={profile.name} recordings={data.recordings} sessions={data.sessions} currentSession={currentSession} options={listOptions} onOptions={setListOptions} onOpen={navigateRecordings} onBack={navigateStandby} loading={data.loading} error={data.error} onRetry={() => void data.reload()} />);
  }

  if (route.page === "detail") {
    const record = data.recordings.find(item => item.id === route.id);
    if (data.error || (!record && data.loading)) return page(`detail:${route.id}`, 3, <RecordingFrame><RecordingHeader title="녹음 상세" backLabel="뒤로가기" onBack={() => navigateRecordings()} /><div className="p-5">{data.error ? <StateView kind="error" message="녹음을 불러오지 못했어요. 다시 시도해 주세요." onRetry={() => void data.reload()} /> : <StateView kind="loading" message="녹음을 불러오는 중이에요…" />}</div></RecordingFrame>);
    if (!record) return page(`detail:${route.id}`, 3, <RecordingFrame><RecordingHeader title="녹음 상세" backLabel="뒤로가기" onBack={() => navigateRecordings()} /><div className="p-5"><StateView kind="empty" title="녹음을 찾을 수 없어요" message="이 감독관의 녹음 목록에 없는 녹음이에요." /></div></RecordingFrame>);
    const filtered = filteredRecordings(data.recordings, currentSession, listOptions);
    const siblings = filtered.some(item => item.id === record.id) ? filtered : data.recordings;
    const index = siblings.findIndex(item => item.id === record.id);
    return page(`detail:${record.id}`, 3, <RecordingDetail key={record.id} supervisorName={profile.name} recording={record} session={data.sessions.find(session => session.id === record.sessionId)} position={index + 1} total={siblings.length} previousId={siblings[index - 1]?.id} nextId={siblings[index + 1]?.id} onOpen={navigateRecordings} onBack={() => navigateRecordings()} onSaved={() => void data.reload()} />, index);
  }

  return page("standby", 1, <>
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
    {confirmEnd && <ConfirmSheet title={confirmEnd === "switch" ? "운행을 종료하고 감독관을 바꿀까요?" : "이번 운행을 종료할까요?"} message="보관한 녹음은 그대로 남아요." confirmLabel={confirmEnd === "switch" ? "종료하고 바꾸기" : "운행 종료"} onCancel={() => setConfirmEnd(null)} onConfirm={() => { const mode = confirmEnd; setConfirmEnd(null); void (mode === "switch" ? changeSession("end", true) : changeSession("end")); }} />}
  </>);
}
