// 기본은 같은 주소의 /api 를 부른다.
// - 개발: vite.config.ts 의 server.proxy 가 /api 를 백엔드로 넘긴다.
// - 배포(Vercel): vercel.json 의 rewrites 가 /api 를 백엔드로 넘긴다.
// 같은 주소로 보이므로 CORS 설정이 필요 없고, 로그인 유지 쿠키(refresh_token)도 그대로 동작한다.
// 다른 주소의 서버를 직접 부르려면 VITE_API_BASE_URL 을 지정한다. (이때는 서버 CORS·쿠키 설정이 필요하다)
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

let accessToken: string | null = null;
let refreshing: Promise<LoginResult | null> | null = null;
const sessionListeners = new Set<() => void>();

export function getApiBaseUrl() {
    return API_BASE_URL;
}

export function getAccessToken() {
    return accessToken;
}

export function setAccessToken(token: string | null) {
    accessToken = token;
}

/** 로그인 유지가 끊겼을 때(재발급 실패) 호출된다. App 이 로그인 화면으로 돌린다. */
export function onSessionExpired(listener: () => void) {
    sessionListeners.add(listener);
    return () => { sessionListeners.delete(listener); };
}

export class ApiError extends Error {
    readonly status: number;
    constructor(status: number, message: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

function rawFetch(path: string, init: RequestInit) {
    const headers = new Headers(init.headers);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: "include" });
}

/** access token 이 만료돼 401 이 오면 한 번만 재발급 받고 다시 보낸다. */
export async function apiFetch(path: string, init: RequestInit = {}) {
    const response = await rawFetch(path, init);
    if (response.status !== 401 || path.startsWith("/api/auth/")) return response;
    const refreshed = await refreshAccessToken(init.signal ?? undefined);
    if (!refreshed) {
        sessionListeners.forEach(listener => listener());
        return response;
    }
    return rawFetch(path, init);
}

async function errorMessage(response: Response, fallback: string) {
    try {
        const body = await response.json() as { detail?: unknown };
        if (typeof body.detail === "string") return body.detail;
        if (body.detail && typeof body.detail === "object" && "message" in body.detail && typeof body.detail.message === "string") return body.detail.message;
    } catch {
        // 본문이 JSON 이 아니면 기본 문구를 쓴다.
    }
    return fallback;
}

/** JSON 을 주고받는 요청. 실패하면 ApiError 를 던진다. */
export async function apiJson<T>(path: string, init: RequestInit & { json?: unknown } = {}, fallback = "서버 요청에 실패했어요."): Promise<T> {
    const { json, ...rest } = init;
    const headers = new Headers(rest.headers);
    if (json !== undefined) headers.set("Content-Type", "application/json");
    const response = await apiFetch(path, { ...rest, headers, ...(json !== undefined ? { body: JSON.stringify(json) } : {}) });
    if (!response.ok) throw new ApiError(response.status, await errorMessage(response, fallback));
    if (response.status === 204) return undefined as T;
    return await response.json() as T;
}

export type UserPublic = {
    id: string;
    display_name: string;
    is_active: boolean;
    role: "operator" | "admin";
};

export type LoginResult = {
    access_token: string;
    expires_in: number;
    user: UserPublic;
};

export async function loginWithCode(code: string, signal?: AbortSignal): Promise<LoginResult> {
    const response = await rawFetch("/api/auth/login", {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
    });

    if (!response.ok) {
        let detail = "로그인하지 못했어요. 다시 시도해 주세요.";
        if (response.status === 422) detail = "로그인 코드 형식을 확인해 주세요.";
        else detail = await errorMessage(response, detail);
        throw new Error(detail);
    }

    const result = await response.json() as LoginResult;
    setAccessToken(result.access_token);
    return result;
}

/**
 * 여러 요청이 동시에 401 을 받아도 재발급은 한 번만 한다.
 * 재발급 요청은 여러 곳이 함께 기다리므로 한 곳이 취소해도 끊지 않는다. (signal 은 받기만 한다)
 */
export function refreshAccessToken(_signal?: AbortSignal): Promise<LoginResult | null> {
    if (!refreshing) {
        refreshing = (async () => {
            try {
                const response = await rawFetch("/api/auth/refresh", { method: "POST" });
                if (!response.ok) { setAccessToken(null); return null; }
                const result = await response.json() as LoginResult;
                setAccessToken(result.access_token);
                return result;
            } catch {
                return null;
            }
        })().finally(() => { refreshing = null; });
    }
    return refreshing;
}

export async function logoutSession(signal?: AbortSignal) {
    try {
        await rawFetch("/api/auth/logout", { method: "POST", signal });
    } finally {
        setAccessToken(null);
    }
}

export async function logoutAllSessions() {
    try {
        await apiJson<void>("/api/auth/logout-all", { method: "POST" }, "모든 기기에서 로그아웃하지 못했어요.");
    } finally {
        setAccessToken(null);
    }
}

export function getMe(signal?: AbortSignal) {
    return apiJson<UserPublic>("/api/auth/me", { signal }, "내 정보를 불러오지 못했어요.");
}

export function updateMyName(displayName: string) {
    return apiJson<UserPublic>("/api/auth/me", { method: "PATCH", json: { display_name: displayName } }, "이름을 바꾸지 못했어요.");
}

export function changeMyCode(currentCode: string, newCode: string) {
    return apiJson<void>("/api/auth/me/code", { method: "PUT", json: { current_code: currentCode, new_code: newCode } }, "로그인 코드를 바꾸지 못했어요.");
}
