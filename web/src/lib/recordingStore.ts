import type { DriveSession, RecordingReview, StoredRecording, SupervisorId } from "@/types/report";

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

export async function countRecordings(supervisorId: SupervisorId): Promise<number> {
  const db = await openStore();
  try {
    return await new Promise<number>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readonly");
      const request = transaction.objectStore(STORE).index("supervisorId").count(supervisorId);
      transaction.oncomplete = () => resolve(request.result);
      transaction.onabort = () => reject(transaction.error);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally { db.close(); }
}

/** 다음 단계의 목록·상세 화면에서 사용할 읽기 기능. */
export async function getRecordings(supervisorId: SupervisorId): Promise<StoredRecording[]> {
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
