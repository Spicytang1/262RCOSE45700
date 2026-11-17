import { MapPin } from "lucide-react";
import type { RecordingLocation } from "@/types/report";
import { dateText, focusStyle, timeText } from "@/lib/recordingPresentation";
import { LOCATION_UNAVAILABLE_TEXT } from "@/lib/recordingLocation";
import { RecordingPanel } from "./RecordingChrome";

export default function RecordingLocationMap({ location }: { location?: RecordingLocation }) {
  if (!location || location.status !== "available") return <RecordingPanel title="녹음 시작 위치"><p className="text-[14px] text-ink-sub">{location ? LOCATION_UNAVAILABLE_TEXT[location.status] : "이 녹음에는 보관한 위치가 없어요. 위치 기록을 추가하기 전의 녹음은 지도에 표시하지 않아요."}</p></RecordingPanel>;

  const { latitude, longitude, accuracy, capturedAt } = location;
  // 현재 일단은 OpenStreetMap 기반 지도로 구현해 놓았다. 추후 지도 제공자 교체 시 이 부분을 변경한다.
  // 공식 공유용 embed를 사용하며, 좌표는 지도 요청에 포함된다. 별도 지도 API 키는 사용하지 않는다.
  const params = new URLSearchParams({
    bbox: [Math.max(-180, longitude - 0.005), Math.max(-90, latitude - 0.003), Math.min(180, longitude + 0.005), Math.min(90, latitude + 0.003)].join(","),
    layer: "mapnik", marker: `${latitude},${longitude}`,
  });

  return <RecordingPanel title="녹음 시작 위치">
    <p className="mb-3 flex items-start gap-2 text-[13px] text-ink-sub"><MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />녹음 버튼을 누를 때 요청한 기기 위치예요. 사건 발생 위치와 다를 수 있어요.</p>
    <iframe title="녹음 시작 위치 지도" src={`https://www.openstreetmap.org/export/embed.html?${params}`} loading="lazy" referrerPolicy="strict-origin-when-cross-origin" className="h-64 w-full rounded-button border border-line bg-surface" />
    <p className="mt-2 text-[11px] text-ink-sub">지도 © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className={`underline underline-offset-2 ${focusStyle}`}>OpenStreetMap 기여자</a></p>
    <dl className="mt-4 space-y-1.5 text-[12px] text-ink-sub">
      <div className="flex flex-wrap gap-x-2"><dt>위도·경도</dt><dd className="tabular-nums">{latitude.toFixed(6)}, {longitude.toFixed(6)}</dd></div>
      <div className="flex flex-wrap gap-x-2"><dt>위치 정확도</dt><dd>약 {Math.round(accuracy).toLocaleString("ko-KR")}m</dd></div>
      <div className="flex flex-wrap gap-x-2"><dt>위치 확인</dt><dd>{dateText(capturedAt)} {timeText(capturedAt)}</dd></div>
    </dl>
    <p className="mt-2 text-[11px] text-ink-sub">지도 표시 시 이 좌표가 지도 서비스에 전달돼요.</p>
  </RecordingPanel>;
}
