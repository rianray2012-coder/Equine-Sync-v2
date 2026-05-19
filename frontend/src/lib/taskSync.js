/**
 * Offline-tolerant Task completion queue.
 *
 * Optimistic UI: completion is reflected in local state instantly while a
 * background worker drains a localStorage-backed queue with exponential backoff.
 * Idempotent on the server via `client_completion_id`.
 */
import { api } from "./api";

const QUEUE_KEY = "equine_task_completion_queue_v1";
const RETRY_DELAYS = [1000, 5000, 15000, 60000, 5 * 60000, 30 * 60000];

const subscribers = new Set();

const load = () => {
  try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); }
  catch { return []; }
};
const save = (q) => {
  try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch {}
  subscribers.forEach((s) => { try { s(q); } catch {} });
};

export const subscribeSyncState = (fn) => {
  subscribers.add(fn);
  fn(load());
  return () => subscribers.delete(fn);
};

export const newClientCompletionId = () =>
  (crypto.randomUUID ? crypto.randomUUID() : `ccid-${Date.now()}-${Math.random().toString(36).slice(2)}`);

let processing = false;

const processQueue = async () => {
  if (processing) return;
  processing = true;
  try {
    let q = load();
    let progressed = true;
    while (progressed) {
      progressed = false;
      q = load();
      for (let i = 0; i < q.length; i++) {
        const item = q[i];
        if (item.state === "synced") continue;
        const now = Date.now();
        if (item.nextAttemptAt && now < item.nextAttemptAt) continue;
        item.state = "syncing";
        item.attempts = (item.attempts || 0) + 1;
        save(q);
        try {
          const path = item.kind === "bulk"
            ? "/tasks/bulk-complete"
            : `/tasks/${item.task_id}/${item.action || "complete"}`;
          await api.post(path, item.body);
          item.state = "synced";
          item.syncedAt = new Date().toISOString();
          progressed = true;
        } catch (err) {
          const status = err?.response?.status;
          // Validation errors are non-retryable
          if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) {
            item.state = "failed";
            item.error = err?.response?.data?.detail || `HTTP ${status}`;
          } else {
            const idx = Math.min(item.attempts - 1, RETRY_DELAYS.length - 1);
            item.nextAttemptAt = Date.now() + RETRY_DELAYS[idx];
            item.state = "queued";
            item.error = err?.message || "network";
          }
        }
        save(q);
      }
      // remove synced items older than 60s to keep queue tidy
      const cutoff = Date.now() - 60_000;
      const cleaned = q.filter((x) => !(x.state === "synced" && x.syncedAt && new Date(x.syncedAt).getTime() < cutoff));
      if (cleaned.length !== q.length) save(cleaned);
    }
  } finally {
    processing = false;
  }
};

// Drain every 4s and when coming back online
setInterval(processQueue, 4000);
if (typeof window !== "undefined") {
  window.addEventListener("online", () => processQueue());
}

export const enqueueComplete = (task_id, { outcome = "done", payload_actual = {}, notes } = {}) => {
  const q = load();
  const client_completion_id = newClientCompletionId();
  q.push({
    id: client_completion_id,
    task_id,
    kind: "single",
    action: "complete",
    state: "queued",
    attempts: 0,
    enqueuedAt: new Date().toISOString(),
    body: {
      client_completion_id,
      outcome,
      payload_actual,
      notes: notes || null,
      completed_at: new Date().toISOString(),
    },
  });
  save(q);
  processQueue();
  return client_completion_id;
};

export const enqueueSkip = (task_id, { refused = false, reason, notes } = {}) => {
  const q = load();
  const client_completion_id = newClientCompletionId();
  q.push({
    id: client_completion_id,
    task_id,
    kind: "single",
    action: "skip",
    state: "queued",
    attempts: 0,
    enqueuedAt: new Date().toISOString(),
    body: { client_completion_id, refused, reason: reason || null, notes: notes || null },
  });
  save(q);
  processQueue();
  return client_completion_id;
};

export const enqueueBulkComplete = (task_ids, { shared_note } = {}) => {
  if (!task_ids.length) return null;
  const q = load();
  const items = task_ids.map((tid) => ({
    task_id: tid,
    client_completion_id: newClientCompletionId(),
    outcome: "done",
    completed_at: new Date().toISOString(),
  }));
  const id = newClientCompletionId();
  q.push({
    id,
    kind: "bulk",
    state: "queued",
    attempts: 0,
    enqueuedAt: new Date().toISOString(),
    body: { items, shared_note: shared_note || null },
    task_ids,
  });
  save(q);
  processQueue();
  return id;
};

export const getPendingForTask = (task_id) =>
  load().filter((x) => x.state !== "synced" &&
    (x.task_id === task_id || (x.kind === "bulk" && x.task_ids?.includes(task_id))));

export const getQueueSummary = () => {
  const q = load();
  return {
    pending: q.filter((x) => x.state === "queued" || x.state === "syncing").length,
    failed: q.filter((x) => x.state === "failed").length,
    total: q.length,
  };
};

export const retryFailed = () => {
  const q = load();
  for (const item of q) {
    if (item.state === "failed") {
      item.state = "queued";
      item.nextAttemptAt = 0;
      item.attempts = 0;
    }
  }
  save(q);
  processQueue();
};

export const clearSynced = () => {
  save(load().filter((x) => x.state !== "synced"));
};
