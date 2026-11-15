import { useCallback, useEffect, useRef, useState } from "react";
import { DIRECTORY_CHANGED, listSupervisors } from "./supervisorDirectory";
import { resolveSupervisor, useSessionProfiles } from "./sessionProfiles";
import type { Supervisor } from "@/types/report";

export default function useSupervisors() {
  const [base, setBase] = useState<Supervisor[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const currentRequest = useRef<AbortController | null>(null);
  const profiles = useSessionProfiles();
  const reload = useCallback(async () => {
    currentRequest.current?.abort();
    const controller = new AbortController();
    currentRequest.current = controller;
    setStatus("loading");
    try {
      const supervisors = await listSupervisors(controller.signal);
      if (!controller.signal.aborted) { setBase(supervisors); setStatus("ready"); }
    } catch { if (!controller.signal.aborted) setStatus("error"); }
  }, []);

  useEffect(() => {
    const lifecycle = new AbortController();
    void Promise.resolve().then(() => { if (!lifecycle.signal.aborted) return reload(); });
    const refresh = () => { void reload(); };
    window.addEventListener(DIRECTORY_CHANGED, refresh);
    return () => { lifecycle.abort(); currentRequest.current?.abort(); window.removeEventListener(DIRECTORY_CHANGED, refresh); };
  }, [reload]);

  return { supervisors: base.map(supervisor => resolveSupervisor(supervisor, profiles)), status, reload };
}
