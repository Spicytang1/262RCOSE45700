import type { DriveSession, RecordingReview, StoredRecording, SupervisorId } from "@/types/report";

// TODO(backend): 아래 보관 함수는 모두 브라우저 IndexedDB 전용이며 서버 송수신이 없다.
// 실제 연동 시 기존 원본을 지우지 말고 서버 저장소와의 이전·동기화 방식을 정한다.
// supervisorId는 화면 필터일 뿐 접근 통제가 아니다. 서버는 로그인 세션으로 소유권을 검증해야 한다.
const DB_NAME = "p3-supervisor-recordings";
const STORE = "recordings";

function openStore(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 2);
    let blocked = false;
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("supervisorId", "supervisorId");
      }
      if (!db.objectStoreNames.contains("sessions")) {
        const sessions = db.createObjectStore("sessions", { keyPath: "id" });
        sessions.createIndex("supervisorId", "supervisorId");
      }
      if (!db.objectStoreNames.contains("reviews")) {
        db.createObjectStore("reviews", { keyPath: "id" });
      }
    };
    request.onsuccess = () => {
      if (blocked) { request.result.close(); return; }
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
    request.onerror = () => reject(request.error);
    request.onblocked = () => {
      blocked = true;
      reject(new Error("다른 창에서 보관함을 사용 중이에요."));
    };
  });
}

/** 같은 ID의 재시도만 허용하고, 기존 녹음은 덮어쓰지 않는다. */
export async function saveRecording(recording: StoredRecording): Promise<void> {
  // TODO(backend): 음성 Blob·녹음 ID·회차 ID·녹음 시각·길이·위치 결과를 업로드하고 서버 보관 완료를 확인한다.
  // 같은 녹음 ID의 재시도는 중복 생성하지 않아야 하며 실패 시 원본과 최초 위치를 유지한다.
  const db = await openStore();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction([STORE, "sessions"], "readwrite");
      const store = transaction.objectStore(STORE);
      const existing = store.get(recording.id);
      existing.onsuccess = () => {
        try {
          if (existing.result) return;
          if (!recording.sessionId) { store.add(recording); return; }
          const sessionRequest = transaction.objectStore("sessions").get(recording.sessionId);
          sessionRequest.onsuccess = () => {
            const session = sessionRequest.result as DriveSession | undefined;
            if (!session || session.endedAt || session.supervisorId !== recording.supervisorId) {
              transaction.abort();
              return;
            }
            try { store.add(recording); } catch { transaction.abort(); }
          };
        } catch {
          transaction.abort();
        }
      };
      transaction.oncomplete = () => resolve();
      transaction.onabort = () => reject(transaction.error ?? new Error("녹음 보관 실패"));
      transaction.onerror = () => reject(transaction.error ?? new Error("녹음 보관 실패"));
    });
  } finally { db.close(); }
}

export async function getSessions(supervisorId: SupervisorId): Promise<DriveSession[]> {
  // TODO(backend): 현재 감독관의 회차 목록과 진행 중 회차를 서버에서 조회한다.
  const db = await openStore();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("sessions", "readonly");
      const req = tx.objectStore("sessions").index("supervisorId").getAll(supervisorId);
      tx.oncomplete = () => resolve((req.result as DriveSession[]).sort((a, b) => b.number - a.number));
      tx.onabort = tx.onerror = () => reject(tx.error);
    });
  } finally { db.close(); }
}

/** 같은 처리 안에서 기존 운행을 확인해 중복 시작을 막는다. */
export async function startSession(supervisorId: SupervisorId): Promise<DriveSession> {
  // TODO(backend): 운행 시작을 서버로 전송하고 확정된 회차 ID·번호·시각을 받는다. 여러 기기의 중복 시작도 서버에서 방지한다.
  const db = await openStore();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("sessions", "readwrite");
      const store = tx.objectStore("sessions");
      const req = store.index("supervisorId").getAll(supervisorId);
      let result: DriveSession;
      req.onsuccess = () => {
        const sessions = req.result as DriveSession[];
        const active = sessions.find(s => !s.endedAt);
        if (active) { result = active; return; }
        result = { id: crypto.randomUUID(), supervisorId, number: Math.max(0, ...sessions.map(s => s.number)) + 1, startedAt: new Date().toISOString(), endedAt: null };
        try { store.add(result); } catch { tx.abort(); }
      };
      tx.oncomplete = () => resolve(result);
      tx.onabort = tx.onerror = () => reject(tx.error ?? new Error("운행 시작 실패"));
    });
  } finally { db.close(); }
}

export async function endSession(id: string, supervisorId: SupervisorId): Promise<void> {
  // TODO(backend): 회차 종료를 서버로 전송하고 소유권·진행 상태를 검증한 완료 응답을 기다린다. 종료 재시도도 안전해야 한다.
  const db = await openStore();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("sessions", "readwrite");
      const store = tx.objectStore("sessions");
      const req = store.get(id);
      req.onsuccess = () => {
        const session = req.result as DriveSession | undefined;
        if (!session || session.supervisorId !== supervisorId) { tx.abort(); return; }
        if (!session.endedAt) {
          try { store.put({ ...session, endedAt: new Date().toISOString() }); } catch { tx.abort(); }
        }
      };
      tx.oncomplete = () => resolve();
      tx.onabort = tx.onerror = () => reject(tx.error ?? new Error("운행 종료 실패"));
    });
  } finally { db.close(); }
}

export async function getReviews(): Promise<RecordingReview[]> {
  // TODO(backend): 현재 사용자가 접근할 수 있는 녹음의 검토 내용만 서버에서 조회한다. 현재는 로컬 전체 검토를 읽는다.
  const db = await openStore();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("reviews", "readonly");
      const req = tx.objectStore("reviews").getAll();
      tx.oncomplete = () => resolve(req.result);
      tx.onabort = tx.onerror = () => reject(tx.error);
    });
  } finally { db.close(); }
}

/** 음성 원본을 변경하지 않고, 선택한 감독관의 검토 내용만 보관한다. */
export async function saveReview(review: RecordingReview, supervisorId: SupervisorId): Promise<void> {
  // TODO(backend): 녹음 ID와 제목·상태·정리 항목·기타 선택·메모를 서버에 저장하고 성공 응답을 기다린다.
  // 기타 입력 보관용 otherFieldValues도 송수신한다. 현재 선택 값(fields)과 구분해 목록·검색에는 선택 값만 사용한다.
  // 원본·자동 분석 결과는 보존하고, 다른 기기의 동시 수정 충돌도 구분한다.
  const db = await openStore();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction([STORE, "reviews"], "readwrite");
      const req = tx.objectStore(STORE).get(review.id);
      req.onsuccess = () => {
        if (req.result?.supervisorId !== supervisorId) { tx.abort(); return; }
        try { tx.objectStore("reviews").put(review); } catch { tx.abort(); }
      };
      tx.oncomplete = () => resolve();
      tx.onabort = tx.onerror = () => reject(tx.error ?? new Error("검토 보관 실패"));
    });
  } finally { db.close(); }
}



/** 다음 단계의 목록·상세 화면에서 사용할 읽기 기능. */
export async function getRecordings(supervisorId: SupervisorId): Promise<StoredRecording[]> {
  // TODO(backend): 녹음 목록·상세·위치·분석 처리 상태를 서버에서 조회하고 음성은 접근 권한이 있는 재생 경로로 받는다.
  // 현재 audio: Blob을 전제로 하므로 응답 자료형·RecordingPlayer·useRecordingData의 원본 참조 유지도 함께 조정한다.
  const db = await openStore();
  try {
    return await new Promise<StoredRecording[]>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readonly");
      const request = transaction.objectStore(STORE).index("supervisorId").getAll(supervisorId);
      transaction.oncomplete = () => resolve(
        (request.result as StoredRecording[]).sort((a, b) => b.recordedAt.localeCompare(a.recordedAt)),
      );
      transaction.onabort = () => reject(transaction.error);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally { db.close(); }
}
