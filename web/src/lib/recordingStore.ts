import type { StoredRecording, SupervisorId } from "@/types/report";

const DB_NAME = "p3-supervisor-recordings";
const STORE = "recordings";

function openStore(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    let blocked = false;
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("supervisorId", "supervisorId");
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
      const transaction = db.transaction(STORE, "readwrite");
      const store = transaction.objectStore(STORE);
      const existing = store.get(recording.id);
      existing.onsuccess = () => {
        try {
          if (!existing.result) store.add(recording);
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
