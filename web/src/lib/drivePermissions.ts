import { captureRecordingLocation } from "./recordingLocation";

export type DrivePermissionStatus = "checking" | "granted" | "denied" | "restricted" | "timeout" | "unavailable" | "unsupported" | "insecure";
export type DrivePermissions = { microphone: DrivePermissionStatus; location: DrivePermissionStatus };
type PermissionKind = keyof DrivePermissions;

async function permissionState(name: "microphone" | "geolocation") {
  try { return (await navigator.permissions.query({ name: name as PermissionName })).state; }
  catch { return null; } // 권한 조회를 지원하지 않는 브라우저는 실제 요청으로 확인한다.
}

function policyBlocks(feature: "microphone" | "geolocation") {
  const page = document as Document & { permissionsPolicy?: { allowsFeature: (name: string) => boolean }; featurePolicy?: { allowsFeature: (name: string) => boolean } };
  try { return (page.permissionsPolicy ?? page.featurePolicy)?.allowsFeature(feature) === false; }
  catch { return false; }
}

// 응답하지 않은 권한 창이 있으면 중복 마이크 요청을 만들지 않는다. 늦게 허용해도 즉시 끈다.
let microphoneRequest: Promise<DrivePermissionStatus> | null = null;
function requestMicrophone() {
  if (!microphoneRequest) {
    microphoneRequest = navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
      stream.getTracks().forEach(track => track.stop());
      return "granted" as const;
    }, (error: unknown): DrivePermissionStatus => error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "SecurityError") ? "denied" : "unavailable").finally(() => { microphoneRequest = null; });
  }
  return microphoneRequest;
}

async function checkMicrophone(signal: AbortSignal): Promise<DrivePermissionStatus> {
  if (!window.isSecureContext) return "insecure";
  if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
  if (policyBlocks("microphone")) return "restricted";
  if (await permissionState("microphone") === "granted") return "granted";
  if (signal.aborted) return "unavailable";
  return new Promise(resolve => {
    let settled = false;
    const finish = (status: DrivePermissionStatus) => {
      if (settled) return;
      settled = true; clearTimeout(timer); signal.removeEventListener("abort", cancel); resolve(status);
    };
    const cancel = () => finish("unavailable");
    const timer = setTimeout(() => finish("timeout"), 10_000);
    signal.addEventListener("abort", cancel, { once: true });
    try { void requestMicrophone().then(finish, () => finish("unavailable")); }
    catch { finish("unavailable"); }
  });
}

async function checkLocation(signal: AbortSignal): Promise<DrivePermissionStatus> {
  if (!window.isSecureContext) return "insecure";
  if (!navigator.geolocation) return "unsupported";
  if (policyBlocks("geolocation")) return "restricted";
  if (await permissionState("geolocation") === "granted") return "granted";
  if (signal.aborted) return "unavailable";
  // 여기서 받은 좌표는 권한 확인용이라 버린다. 녹음 위치는 녹음 버튼에서 새로 받는다.
  const result = await captureRecordingLocation(signal);
  if (result.status === "available" || await permissionState("geolocation") === "granted") return "granted";
  return result.status;
}

/** 운행 시작마다 재확인한다. 이미 허용된 권한은 실제 요청을 생략한다. */
export async function requestDrivePermissions(signal: AbortSignal, onUpdate: (kind: PermissionKind, status: DrivePermissionStatus) => void) {
  const run = async (kind: PermissionKind, check: (signal: AbortSignal) => Promise<DrivePermissionStatus>) => {
    try { const status = await check(signal); if (!signal.aborted) onUpdate(kind, status); }
    catch { if (!signal.aborted) onUpdate(kind, "unavailable"); }
  };
  await Promise.all([run("microphone", checkMicrophone), run("location", checkLocation)]);
}
