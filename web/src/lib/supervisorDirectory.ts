import type { Supervisor, SupervisorId } from "@/types/report";

/** 실제 연결 시 목록 조회·로그인 검증 구현만 교체한다. 비밀번호를 목록에 넣지 않는다. */
export type SupervisorDirectory = {
  mode: "demo" | "backend";
  list: (signal?: AbortSignal) => Promise<Supervisor[]>;
  authenticate: (id: SupervisorId, pin: string, signal?: AbortSignal) => Promise<boolean>;
};

const demoDirectory: SupervisorDirectory = {
  mode: "demo",
  list: async () => Array.from({ length: 6 }, (_, index) => ({ id: index + 1, name: `감독관 ${index + 1}`, photoUrl: null })),
  authenticate: async (_id, pin) => pin === "1234",
};

let directory = demoDirectory;
export const DIRECTORY_CHANGED = "p3-supervisor-directory-changed";
export const supervisorKey = (id: SupervisorId) => `${typeof id}:${id}`;
export const getSupervisorDirectory = () => directory;

/** 관리자 기능이 아니라, 앱 초기화 시 실제 제공자를 주입하기 위한 연결 지점이다. */
export function configureSupervisorDirectory(next: SupervisorDirectory) {
  directory = next;
  window.dispatchEvent(new Event(DIRECTORY_CHANGED));
}

export async function listSupervisors(signal?: AbortSignal): Promise<Supervisor[]> {
  const result = await directory.list(signal);
  if (!Array.isArray(result)) throw new Error("감독관 목록 형식을 확인해 주세요.");
  const seen = new Set<string>();
  return result.map(supervisor => {
    const id = supervisor?.id;
    if ((typeof id !== "string" && typeof id !== "number") || (typeof id === "number" && !Number.isFinite(id)) || String(id).trim() === "" || typeof supervisor.name !== "string" || !supervisor.name.trim()) {
      throw new Error("감독관 정보 형식을 확인해 주세요.");
    }
    const key = supervisorKey(id);
    if (seen.has(key)) throw new Error("중복된 감독관 정보가 있어요.");
    seen.add(key);
    return { id, name: supervisor.name.trim(), photoUrl: typeof supervisor.photoUrl === "string" ? supervisor.photoUrl : null };
  });
}
