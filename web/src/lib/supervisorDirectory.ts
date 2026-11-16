import type { Supervisor, SupervisorId } from "@/types/report";

/** 실제 연결 시 목록 조회·로그인 검증 구현만 교체한다. 비밀번호를 목록에 넣지 않는다. */
export type SupervisorDirectory = {
  mode: "demo" | "backend";
  list: (signal?: AbortSignal) => Promise<Supervisor[]>;
  authenticate: (id: SupervisorId, pin: string, signal?: AbortSignal) => Promise<boolean>;
};

// 시연용 감독관 계정과 개인 PIN (실제 연결 시 서버 응답으로 교체한다)
const demoAccounts: { id: number; name: string; pin: string }[] = [
  { id: 1, name: "정해인", pin: "1111" },
  { id: 2, name: "김우빈", pin: "1234" },
  { id: 3, name: "이종석", pin: "4567" },
  { id: 4, name: "강동원", pin: "2323" },
  { id: 5, name: "손예진", pin: "9878" },
  { id: 6, name: "김유정", pin: "6543" },
];

// TODO(backend): 고정 목록 대신 서버에서 감독관 고유 ID·표시 이름·사진 URL 목록을 조회한다.
// TODO(backend): 공통 PIN 비교 대신 PIN을 보안 연결로 전송해 검증하고 서버 로그인 세션을 발급받는다.
// 목록 응답에는 PIN·해시를 포함하지 않고, 실패 횟수 제한과 접근 권한 검사는 서버에서 수행한다.
const demoDirectory: SupervisorDirectory = {
  mode: "demo",
  list: async () => demoAccounts.map(({ id, name }) => ({ id, name, photoUrl: null })),
  authenticate: async (id, pin) => demoAccounts.some(account => account.id === id && account.pin === pin),
};

// TODO(backend): 앱 초기화 시 configureSupervisorDirectory로 실제 제공자를 주입한다. 미연결 시 시연 로그인이 유지된다.
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

/** PIN 4자리로 감독관을 찾는다. 일치하는 감독관이 없으면 null을 돌려준다. */
export async function findSupervisorByPin(pin: string): Promise<Supervisor | null> {
  const found = demoAccounts.find(account => account.pin === pin);
  return found ? { id: found.id, name: found.name, photoUrl: null } : null;
}
