import { useEffect, useState } from "react";
import { MapPin, WifiOff } from "lucide-react";
import type { RecordingLocation } from "@/types/report";
import { dateText, focusStyle, timeText } from "@/lib/recordingPresentation";
import { LOCATION_UNAVAILABLE_TEXT } from "@/lib/recordingLocation";
import { RecordingFold } from "./RecordingChrome";

export default function RecordingLocationMap({ location }: { location?: RecordingLocation }) {
  const [state, setState] = useState<"idle" | "loading" | "ready" | "failed">("idle");

  useEffect(() => {
    if (state !== "loading") return;
    const timer = setTimeout(() => setState("failed"), 10000);
    return () => clearTimeout(timer);
  }, [state]);

  if (!location || location.status !== "available") return <RecordingFold title="녹음 시작 위치"><p className="text-[14px] text-ink-sub">{location ? LOCATION_UNAVAILABLE_TEXT[location.status] : "이 녹음에는 보관한 위치가 없어요. 위치 기록을 추가하기 전의 녹음은 지도에 표시하지 않아요."}</p></RecordingFold>;

  const { latitude, longitude, accuracy, capturedAt } = location;
  // 현재 일단은 OpenStreetMap 기반 지도로 구현해 놓았다. 추후 지도 제공자 교체 시 이 부분을 변경한다.
  // 공식 공유용 embed를 사용하며, 좌표는 지도 요청에 포함된다. 별도 지도 API 키는 사용하지 않는다.
  const params = new URLSearchParams({
    bbox: [Math.max(-180, longitude - 0.005), Math.max(-90, latitude - 0.003), Math.min(180, longitude + 0.005), Math.min(90, latitude + 0.003)].join(","),
    layer: "mapnik", marker: `${latitude},${longitude}`,
  });

  return <RecordingFold title="녹음 시작 위치" onOpen={() => setState(current => current === "idle" ? "loading" : current)}>
    <p className="mb-3 flex items-start gap-2 text-[13px] text-ink-sub"><MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />녹음 버튼을 누를 때 요청한 기기 위치예요. 사건 발생 위치와 다를 수 있어요.</p>
    <div className="relative h-64 w-full overflow-hidden rounded-button border border-line bg-surface">
      {state !== "idle" && state !== "failed" && <iframe title="녹음 시작 위치 지도" src={`https://www.openstreetmap.org/export/embed.html?${params}`} onLoad={() => setState("ready")} referrerPolicy="strict-origin-when-cross-origin" className="size-full" />}
      {state === "loading" && <div role="status" className="absolute inset-0 flex items-center justify-center bg-surface text-[13px] text-ink-sub"><span aria-hidden="true" className="mr-2 size-4 animate-spin rounded-full border-2 border-line border-t-ink motion-reduce:animate-none" />지도를 불러오고 있어요…</div>}
      {state === "failed" && <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-[13px] text-ink-sub"><WifiOff className="size-6" aria-hidden="true" /><p>지도를 불러오지 못했어요. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.</p><button type="button" onClick={() => setState("loading")} className={`min-h-11 rounded-button bg-white px-4 text-[13px] font-bold text-ink shadow-card ${focusStyle}`}>다시 시도</button></div>}
    </div>
    <p className="mt-2 text-[11px] text-ink-sub">지도 © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className={`underline underline-offset-2 ${focusStyle}`}>OpenStreetMap 기여자</a></p>
    <dl className="mt-4 space-y-1.5 text-[12px] text-ink-sub">
      <div className="flex flex-wrap gap-x-2"><dt>위도·경도</dt><dd className="tabular-nums">{latitude.toFixed(6)}, {longitude.toFixed(6)}</dd></div>
      <div className="flex flex-wrap gap-x-2"><dt>위치 정확도</dt><dd>약 {Math.round(accuracy).toLocaleString("ko-KR")}m</dd></div>
      <div className="flex flex-wrap gap-x-2"><dt>위치 확인</dt><dd>{dateText(capturedAt)} {timeText(capturedAt)}</dd></div>
    </dl>
    <p className="mt-2 text-[11px] text-ink-sub">지도 표시 시 이 좌표가 지도 서비스에 전달돼요.</p>
  </RecordingFold>;
}
