import type { RecordingLocation } from "@/types/report";

/** 위치가 늦거나 거부되어도 마이크 시작을 막지 않는다. 결과는 해당 녹음에만 귀속한다. */
export function captureRecordingLocation(signal: AbortSignal): Promise<RecordingLocation> {
  const requestedAt = new Date().toISOString();
  if (!window.isSecureContext) return Promise.resolve({ status: "insecure", requestedAt });
  if (!navigator.geolocation) return Promise.resolve({ status: "unsupported", requestedAt });
  if (signal.aborted) return Promise.resolve({ status: "unavailable", requestedAt });

  return new Promise(resolve => {
    let settled = false;
    const finish = (result: RecordingLocation) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal.removeEventListener("abort", cancel);
      resolve(result);
    };
    const cancel = () => finish({ status: "unavailable", requestedAt });
    // 브라우저의 timeout에는 권한 응답 대기가 포함되지 않을 수 있어 별도 상한도 둔다.
    const timer = setTimeout(() => finish({ status: "timeout", requestedAt }), 10_000);
    signal.addEventListener("abort", cancel, { once: true });
    try {
      navigator.geolocation.getCurrentPosition(position => {
        const { latitude, longitude, accuracy } = position.coords;
        if (!Number.isFinite(latitude) || Math.abs(latitude) > 90 || !Number.isFinite(longitude) || Math.abs(longitude) > 180 || !Number.isFinite(accuracy) || accuracy < 0 || !Number.isFinite(position.timestamp)) {
          finish({ status: "unavailable", requestedAt }); return;
        }
        finish({ status: "available", requestedAt, latitude, longitude, accuracy, capturedAt: new Date(position.timestamp).toISOString() });
      }, error => finish({ status: error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable", requestedAt }), { enableHighAccuracy: true, maximumAge: 0, timeout: 8_000 });
    } catch { finish({ status: "unavailable", requestedAt }); }
  });
}

export const LOCATION_UNAVAILABLE_TEXT = {
  denied: "위치 권한이 허용되지 않아 저장된 위치가 없어요. 다음 녹음부터 위치를 남기려면 브라우저에서 위치 권한을 허용해 주세요.",
  timeout: "녹음을 시작할 때 위치를 제때 확인하지 못했어요. 음성은 정상적으로 보관했어요.",
  unavailable: "녹음을 시작할 때 위치를 확인하지 못했어요. 기기의 위치 설정을 확인해 주세요. 음성은 정상적으로 보관했어요.",
  unsupported: "이 브라우저에서 위치 기능을 사용할 수 없어 위치 없이 음성만 보관했어요.",
  insecure: "보안 연결이 아니라서 위치를 받지 못했어요. 음성만 보관했어요. 보안 연결로 열고 다시 녹음해 주세요.",
} as const;
