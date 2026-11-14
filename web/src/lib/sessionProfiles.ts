import { useSyncExternalStore } from "react";
import type { Supervisor, SupervisorId } from "@/types/report";
import { getSupervisorDirectory, listSupervisors, supervisorKey } from "./supervisorDirectory";

type ProfileOverride = { name?: string; photoUrl?: string | null; pinSalt?: string; pinHash?: string };
type Profiles = Record<string, ProfileOverride>;
const STORAGE_KEY = "p3-supervisor-profiles-session-v1";

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
        ...(typeof data.pinSalt === "string" && typeof data.pinHash === "string" ? { pinSalt: data.pinSalt, pinHash: data.pinHash } : {}),
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
  const trimmed = name.trim();
  if (!trimmed || trimmed.length > 40) throw new Error("이름은 1~40자로 입력해 주세요.");
  updateProfile(id, { name: trimmed, photoUrl });
}

async function hashPin(salt: string, pin: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${salt}:${pin}`));
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

/** 실제 계정 보안이 아닌, 현재 탭에서만 사용하는 시연용 검증이다. */
export async function authenticateSupervisor(id: SupervisorId, pin: string, signal?: AbortSignal): Promise<boolean> {
  const directory = getSupervisorDirectory();
  const supervisors = await listSupervisors(signal);
  if (signal?.aborted || !supervisors.some(supervisor => supervisor.id === id)) return false;
  const profile = profiles[supervisorKey(id)];
  if (directory.mode === "demo" && profile?.pinSalt && profile.pinHash) {
    return await hashPin(profile.pinSalt, pin) === profile.pinHash;
  }
  return directory.authenticate(id, pin, signal);
}

export async function changeSessionPassword(id: SupervisorId, current: string, next: string) {
  if (getSupervisorDirectory().mode !== "demo") throw new Error("실제 비밀번호 변경은 계정 관리 기능과 연결해야 해요.");
  if (!/^\d{4}$/.test(current) || !/^\d{4}$/.test(next)) throw new Error("비밀번호는 숫자 4자리로 입력해 주세요.");
  if (!await authenticateSupervisor(id, current)) throw new Error("현재 비밀번호가 맞지 않아요.");
  const salt = crypto.randomUUID();
  const pinHash = await hashPin(salt, next);
  updateProfile(id, { pinSalt: salt, pinHash });
}
