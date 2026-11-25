import { useSyncExternalStore } from "react";
import type { Supervisor, SupervisorId } from "@/types/report";
import { supervisorKey } from "./supervisorDirectory";

type ProfileOverride = { name?: string; photoUrl?: string | null };
type Profiles = Record<string, ProfileOverride>;
const STORAGE_KEY = "p3-supervisor-profiles-session-v1";

// TODO(backend): 현재 탭 전용 프로필 덮어쓰기다. 실제 계정 설정으로 전환할 때 서버의 현재 감독관 프로필을 조회한다.
function readProfiles(): Profiles {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const profiles: Profiles = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (!value || typeof value !== "object" || Array.isArray(value)) continue;
      const data = value as ProfileOverride;
      profiles[key] = {
        ...(typeof data.name === "string" && data.name.trim() ? { name: data.name.trim() } : {}),
        ...(data.photoUrl === null || (typeof data.photoUrl === "string" && data.photoUrl.startsWith("data:image/jpeg;base64,")) ? { photoUrl: data.photoUrl } : {}),
      };
    }
    return profiles;
  } catch { return {}; }
}

let profiles = readProfiles();
const listeners = new Set<() => void>();
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function useSessionProfiles() { return useSyncExternalStore(subscribe, () => profiles); }

function updateProfile(id: SupervisorId, patch: ProfileOverride) {
  const key = supervisorKey(id);
  const next = { ...profiles, [key]: { ...profiles[key], ...patch } };
  // 보관 성공 전에 화면에 성공을 반영하지 않는다.
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next)); }
  catch { throw new Error("설정을 보관하지 못했어요. 탭의 저장 공간과 저장 허용 여부를 확인하고 다시 시도해 주세요."); }
  profiles = next;
  listeners.forEach(listener => listener());
}

export function resolveSupervisor(supervisor: Supervisor, overrides: Profiles): Supervisor {
  const profile = overrides[supervisorKey(supervisor.id)];
  return { ...supervisor, name: profile?.name ?? supervisor.name, photoUrl: profile?.photoUrl === undefined ? supervisor.photoUrl : profile.photoUrl };
}

export function applySessionProfile(id: SupervisorId, name: string, photoUrl: string | null) {
  // TODO(backend): 이름·사진 변경을 서버에 저장하고 확정된 프로필을 반영한다. 사진은 현재 data URL이며 업로드 후 URL로 교체한다.
  // 이 함수가 비동기가 되면 Settings의 적용 처리도 응답을 기다리고 실패 시 입력을 유지하도록 변경한다.
  const trimmed = name.trim();
  if (!trimmed || trimmed.length > 40) throw new Error("이름은 1~40자로 입력해 주세요.");
  updateProfile(id, { name: trimmed, photoUrl });
}

