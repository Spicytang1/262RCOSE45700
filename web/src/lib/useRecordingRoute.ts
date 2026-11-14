import { useSyncExternalStore } from "react";

let navigationGuard: (() => boolean | Promise<boolean>) | null = null;
let acceptedHash = window.location.hash;
export function setRecordingNavigationGuard(guard: () => boolean | Promise<boolean>) {
  navigationGuard = guard;
  return () => { if (navigationGuard === guard) navigationGuard = null; };
}

function subscribe(onChange: () => void) {
  let previousUrl = window.location.href;
  let navigationId = 0;
  const update = async () => {
    const request = ++navigationId;
    const targetUrl = window.location.href;
    if (targetUrl !== previousUrl && navigationGuard) {
      window.history.replaceState(null, "", previousUrl);
      const allowed = await navigationGuard();
      if (!allowed || request !== navigationId) return;
      window.history.replaceState(null, "", targetUrl);
    }
    previousUrl = window.location.href;
    acceptedHash = window.location.hash;
    onChange();
  };
  window.addEventListener("hashchange", update);
  return () => window.removeEventListener("hashchange", update);
}

export function navigateRecordings(id?: string) {
  window.location.hash = id ? `/recordings/${encodeURIComponent(id)}` : "/recordings";
}

export function navigateStandby() { window.location.hash = ""; }

export default function useRecordingRoute() {
  const hash = useSyncExternalStore(subscribe, () => acceptedHash);
  if (hash.startsWith("#/recordings/")) {
    try { return { page: "detail" as const, id: decodeURIComponent(hash.slice("#/recordings/".length)) }; }
    catch { return { page: "list" as const }; }
  }
  return { page: hash === "#/recordings" ? "list" as const : "standby" as const };
}
