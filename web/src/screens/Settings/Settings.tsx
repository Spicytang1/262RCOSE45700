import { useEffect, useRef, useState } from "react";
import { Camera, RotateCcw } from "lucide-react";
import ProfileAvatar from "@/components/ProfileAvatar";
import { RecordingFrame, RecordingHeader, RecordingPanel } from "@/screens/Recordings/RecordingChrome";
import { focusStyle } from "@/lib/recordingPresentation";
import { applySessionProfile } from "@/lib/sessionProfiles";
import { prepareProfilePhoto } from "@/lib/profilePhoto";
import { setRecordingNavigationGuard } from "@/lib/useRecordingRoute";
import type { Supervisor } from "@/types/report";

export default function Settings({ profile, onBack }: { profile: Supervisor; onBack: () => void }) {
  const [name, setName] = useState(profile.name);
  const [photoUrl, setPhotoUrl] = useState(profile.photoUrl);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileNotice, setProfileNotice] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const locked = useRef(false);
  const mounted = useRef(true);
  const profileDirty = name !== profile.name || photoUrl !== profile.photoUrl;
  const dirty = profileDirty;
  const busy = photoBusy;
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

  function applyProfile(event: React.FormEvent) {
    // TODO(backend): applySessionProfile을 서버 저장으로 바꾸면 비동기 처리·중복 제출 방지·성공 응답 프로필 반영을 연결한다.
    event.preventDefault();
    if (locked.current) return;
    setProfileError(""); setProfileNotice("");
    if (!name.trim() || name.trim().length > 40) { setProfileError("이름은 1~40자로 입력해 주세요."); document.getElementById("profile-name")?.focus(); return; }
    try { applySessionProfile(profile.id, name, photoUrl); setName(name.trim()); setProfileNotice("이름과 사진을 적용했어요."); }
    catch { setProfileError("설정을 보관하지 못했어요. 탭의 저장 공간과 저장 허용 여부를 확인하고 다시 시도해 주세요."); }
  }

  return <RecordingFrame>
    <RecordingHeader title="환경설정" backLabel="대기" onBack={onBack} />
    <div className="flex flex-col gap-5 px-5 pt-5 pb-8">
      <p className="rounded-card bg-kakao-soft p-4 text-[13px] leading-[1.8]">현재 감독관의 설정이에요. 이 탭을 닫기 전까지만 유지되며, 다른 기기에는 반영되지 않아요. 실제 계정의 이름·비밀번호를 바꾸는 기능은 아니에요.</p>
      <RecordingPanel title="프로필">
        <form onSubmit={applyProfile} noValidate className="flex flex-col gap-5">
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
    </div>
  </RecordingFrame>;
}
