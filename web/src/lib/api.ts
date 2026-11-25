const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "")
    ?? "http://44.223.98.215:8000";

let accessToken: string | null = null;

export function getApiBaseUrl() {
    return API_BASE_URL;
}

export function getAccessToken() {
    return accessToken;
}

export function setAccessToken(token: string | null) {
    accessToken = token;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: "include" });
}

export type LoginResult = {
    access_token: string;
    expires_in: number;
    user: {
        id: string;
        display_name: string;
        is_active: boolean;
        role: "operator" | "admin";
    };
};

export async function loginWithCode(code: string, signal?: AbortSignal): Promise<LoginResult> {
    const response = await apiFetch("/api/auth/login", {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
    });

    if (!response.ok) {
        let detail = "로그인하지 못했어요. 다시 시도해 주세요.";
        try {
            const body = await response.json() as { detail?: string | unknown[] };
            if (typeof body.detail === "string") detail = body.detail;
            else if (response.status === 422) detail = "로그인 코드 형식을 확인해 주세요.";
        } catch {
            // 기본 오류 메시지를 사용한다.
        }
        throw new Error(detail);
    }

    const result = await response.json() as LoginResult;
    setAccessToken(result.access_token);
    return result;
}

export async function refreshAccessToken(signal?: AbortSignal): Promise<LoginResult | null> {
    const response = await apiFetch("/api/auth/refresh", { method: "POST", signal });
    if (!response.ok) {
        setAccessToken(null);
        return null;
    }
    const result = await response.json() as LoginResult;
    setAccessToken(result.access_token);
    return result;
}

export async function logoutSession(signal?: AbortSignal) {
    try {
        await apiFetch("/api/auth/logout", { method: "POST", signal });
    } finally {
        setAccessToken(null);
    }
}
