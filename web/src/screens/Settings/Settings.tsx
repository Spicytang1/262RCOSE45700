import { useEffect, useRef, useState } from "react";
import { Camera, RotateCcw } from "lucide-react";
import ProfileAvatar from "@/components/ProfileAvatar";
import { RecordingFrame, RecordingHeader, RecordingPanel } from "@/screens/Recordings/RecordingChrome";
import { focusStyle } from "@/lib/recordingPresentation";
import { applySessionProfile } from "@/lib/sessionProfiles";
import { changeMyCode, logoutAllSessions, updateMyName } from "@/lib/api";
import { prepareProfilePhoto } from "@/lib/profilePhoto";
import { setRecordingNavigationGuard } from "@/lib/useRecordingRoute";
import type { Supervisor } from "@/types/report";

export default function Settings({ profile, onBack, onNameChange, onLoggedOut }: { profile: Supervisor; onBack: () => void; onNameChange: (name: string) => void; onLoggedOut: () => void }) {
  const [name, setName] = useState(profile.name);
  const [photoUrl, setPhotoUrl] = useState(profile.photoUrl);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileNotice, setProfileNotice] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [codes, setCodes] = useState({ current: "", next: "" });
  const [codeMessage, setCodeMessage] = useState<{ kind: "error" | "ok"; text: string } | null>(null);
  const [codeBusy, setCodeBusy] = useState(false);
  const locked = useRef(false);
  const mounted = useRef(true);
  const profileDirty = name !== profile.name || photoUrl !== profile.photoUrl;
  const dirty = profileDirty;
  const busy = photoBusy || saving;
  const guardState = useRef({ dirty, busy });
  useEffect(() => { guardState.current = { dirty, busy }; }, [dirty, busy]);
  const control = `w-full min-h-12 rounded-button border border-line bg-white px-3 text-[15px] ${focusStyle}`;

  useEffect(() => {
    mounted.current = true;
    const remove = setRecordingNavigationGuard(() => !guardState.current.busy && (!guardState.current.dirty || window.confirm("적용하지 않은 변경 내용이 있어요. 변경 내용을 버리고 이동할까요?")));
    const warn = (event: BeforeUnloadEvent) => {
      if (!guardState.current.dirty && !guardState.current.busy) return;
      event.preventDefault(); event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => { mounted.current = false; remove(); window.removeEventListener("beforeunload", warn); };
  }, []);

  async function selectPhoto(file: File | undefined) {
    if (!file || locked.current) return;
    locked.current = true; setPhotoBusy(true); setProfileError(""); setProfileNotice("");
    try { const photo = await prepareProfilePhoto(file); if (mounted.current) setPhotoUrl(photo); }
    catch (error) { if (mounted.current) setProfileError(error instanceof Error ? error.message : "사진을 준비하지 못했어요."); }
    finally { locked.current = false; if (mounted.current) setPhotoBusy(false); }
  }

  /** 이름은 서버 계정에 저장한다. 사진은 서버에 저장 기능이 없어 이 탭에만 적용한다. */
  async function applyProfile(event: React.FormEvent) {
    event.preventDefault();
    if (locked.current) return;
    setProfileError(""); setProfileNotice("");
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 40) { setProfileError("이름은 1~40자로 입력해 주세요."); document.getElementById("profile-name")?.focus(); return; }
    locked.current = true; setSaving(true);
    try {
      if (trimmed !== profile.name) { const user = await updateMyName(trimmed); onNameChange(user.display_name); }
      applySessionProfile(profile.id, trimmed, photoUrl);
      if (mounted.current) { setName(trimmed); setProfileNotice("이름과 사진을 적용했어요."); }
    } catch (error) { if (mounted.current) setProfileError(error instanceof Error ? error.message : "이름을 바꾸지 못했어요."); }
    finally { locked.current = false; if (mounted.current) setSaving(false); }
  }

  async function submitCode(event: React.FormEvent) {
    event.preventDefault();
    if (codeBusy) return;
    if (!/^(?=.*[A-Za-z])(?=.*\d).{8,64}$/.test(codes.next)) { setCodeMessage({ kind: "error", text: "새 코드는 영문과 숫자를 모두 넣어 8~64자로 입력해 주세요." }); return; }
    setCodeBusy(true); setCodeMessage(null);
    try { await changeMyCode(codes.current, codes.next); setCodes({ current: "", next: "" }); setCodeMessage({ kind: "ok", text: "로그인 코드를 바꿨어요. 다음 로그인부터 새 코드를 써 주세요." }); }
    catch (error) { setCodeMessage({ kind: "error", text: error instanceof Error ? error.message : "로그인 코드를 바꾸지 못했어요." }); }
    finally { setCodeBusy(false); }
  }

  async function logoutEverywhere() {
    if (!window.confirm("이 기기를 포함한 모든 기기에서 로그아웃할까요?")) return;
    try { await logoutAllSessions(); } catch { /* 이 기기는 그대로 로그아웃한다. */ }
    onLoggedOut();
  }

  return <RecordingFrame>
    <RecordingHeader title="환경설정" backLabel="대기" onBack={onBack} />
    <div className="flex flex-col gap-5 px-5 pt-5 pb-8">
      <p className="rounded-card bg-kakao-soft p-4 text-[13px] leading-[1.8]">이름과 로그인 코드는 서버 계정에 저장돼요. 사진은 이 탭에서만 보여요.</p>
      <RecordingPanel title="프로필">
        <form onSubmit={event => void applyProfile(event)} noValidate className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-4">
            <ProfileAvatar profile={{ name: name || profile.name, photoUrl }} size="large" />
            <div className="flex flex-col gap-1">
              <input ref={fileInput} id="profile-photo" name="profile-photo" type="file" accept="image/jpeg,image/png,image/webp" aria-label="프로필 사진 파일" disabled={busy} className="sr-only" tabIndex={-1} onChange={event => { void selectPhoto(event.target.files?.[0]); event.target.value = ""; }} />
              <button type="button" disabled={busy} onClick={() => fileInput.current?.click()} className={`flex min-h-11 items-center gap-2 rounded-button bg-surface px-3 text-[13px] font-bold disabled:opacity-40 ${focusStyle}`}><Camera className="size-4" aria-hidden="true" />{photoBusy ? "사진 준비 중…" : "사진 선택"}</button>
              <button type="button" disabled={busy || !photoUrl} onClick={() => { setPhotoUrl(null); setProfileNotice(""); setProfileError(""); }} className={`flex min-h-11 items-center gap-2 rounded-button px-3 text-[12px] text-ink-sub disabled:opacity-40 ${focusStyle}`}><RotateCcw className="size-3.5" aria-hidden="true" />기본 이미지로</button>
            </div>
          </div>
          <p className="text-[12px] text-ink-sub">JPG·PNG·WebP, 10MB 이하 · 가운데를 정사각형으로 잘라요.</p>
          <div><label htmlFor="profile-name" className="mb-2 block text-[14px] font-bold">감독관 이름 *</label><input id="profile-name" name="profile-name" required aria-invalid={!!profileError} autoComplete="name" value={name} maxLength={40} disabled={busy} onChange={event => { setName(event.target.value); setProfileNotice(""); setProfileError(""); }} className={control} /></div>
          {profileError && <p role="alert" className="text-[13px] text-danger-ink">{profileError}</p>}
          {profileNotice && <p role="status" className="text-[13px] text-ink-sub">{profileNotice}</p>}
          <button type="submit" disabled={busy || !profileDirty} className={`min-h-12 rounded-button bg-kakao px-4 font-bold disabled:opacity-40 ${focusStyle}`}>이름·사진 적용</button>
        </form>
      </RecordingPanel>
      <p className="text-[12px] text-ink-sub">이름을 바꿔도 기존 녹음과 운행 회차는 그대로 남아요.</p>
      <RecordingPanel title="로그인 코드 변경">
        <form onSubmit={event => void submitCode(event)} className="flex flex-col gap-3">
          <div><label htmlFor="code-current" className="mb-2 block text-[14px] font-bold">지금 코드</label><input id="code-current" type="password" autoComplete="current-password" value={codes.current} disabled={codeBusy} onChange={event => setCodes(value => ({ ...value, current: event.target.value }))} className={control} /></div>
          <div><label htmlFor="code-next" className="mb-2 block text-[14px] font-bold">새 코드</label><input id="code-next" type="password" autoComplete="new-password" value={codes.next} disabled={codeBusy} onChange={event => setCodes(value => ({ ...value, next: event.target.value }))} className={control} /><p className="mt-1 text-[12px] text-ink-sub">영문과 숫자를 모두 넣어 8자 이상</p></div>
          {codeMessage && <p role={codeMessage.kind === "error" ? "alert" : "status"} className={`text-[13px] ${codeMessage.kind === "error" ? "text-danger-ink" : "text-ink-sub"}`}>{codeMessage.text}</p>}
          <button type="submit" disabled={codeBusy || !codes.current || !codes.next} className={`min-h-12 rounded-button bg-ink px-4 font-bold text-white disabled:opacity-40 ${focusStyle}`}>{codeBusy ? "바꾸는 중…" : "코드 바꾸기"}</button>
        </form>
      </RecordingPanel>
      <button type="button" onClick={() => void logoutEverywhere()} className={`min-h-12 rounded-button border border-line bg-white px-4 text-[14px] font-bold text-danger-ink ${focusStyle}`}>모든 기기에서 로그아웃</button>
    </div>
  </RecordingFrame>;
}
