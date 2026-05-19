/**
 * Offline-tolerant Task completion queue.
 *
 * Optimistic UI: completion is reflected in local state instantly while a
 * background worker drains a localStorage-backed queue with exponential
 * backoff. Idempotent on the server via `client_completion_id`.
 */
import { api } from "./api";

const QUEUE_KEY = "equine_task_completion_queue_v1";
const RETRY_DELAYS = [1000, 5000, 15000, 60000, 5 * 60000, 30 * 60000];
const SYNCED_TTL_MS = 60_000;

const subscribers = new Set();

// ── storage helpers ────────────────────────────────────────────────────────
const load = () => {
  try {
    return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
  } catch (err) {
    console.warn("[taskSync] queue read failed", err);
    return [];
  }
};

const save = (q) => {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
  } catch (err) {
    console.warn("[taskSync] queue write failed", err);
  }
  subscribers.forEach((s) => {
    try { s(q); } catch (err) { console.warn("[taskSync] subscriber error", err); }
  });
};

export const subscribeSyncState = (fn) => {
  subscribers.add(fn);
  fn(load());
  return () => subscribers.delete(fn);
};

export const newClientCompletionId = () =>
  crypto.randomUUID
    ? crypto.randomUUID()
    : `ccid-${Date.now()}-${Math.random().toString(36).slice(2)}`;

// ── request shaping ───────────────────────────────────────────────────────
const requestPathFor = (item) => {
  if (item.kind === "bulk") return "/tasks/bulk-complete";
  return `/tasks/${item.task_id}/${item.action || "complete"}`;
};

const isNonRetryableStatus = (status) =>
  Boolean(status && status >= 400 && status < 500 && status !== 408 && status !== 429);

const scheduleRetry = (item) => {
  const idx = Math.min(item.attempts - 1, RETRY_DELAYS.length - 1);
  item.nextAttemptAt = Date.now() + RETRY_DELAYS[idx];
  item.state = "queued";
};

const markFailed = (item, err) => {
  item.state = "failed";
  item.error = err?.response?.data?.detail || `HTTP ${err?.response?.status}`;
};

const markSynced = (item) => {
  item.state = "synced";
  item.syncedAt = new Date().toISOString();
};

// ── single-item attempt; returns true if state changed ────────────────────
const attemptItem = async (item, q) => {
  if (item.state === "synced") return false;
  if (item.nextAttemptAt && Date.now() < item.nextAttemptAt) return false;

  item.state = "syncing";
  item.attempts = (item.attempts || 0) + 1;
  save(q);

  try {
    await api.post(requestPathFor(item), item.body);
    markSynced(item);
  } catch (err) {
    if (isNonRetryableStatus(err?.response?.status)) {
      markFailed(item, err);
    } else {
      scheduleRetry(item);
      item.error = err?.message || "network";
    }
  }
  save(q);
  return true;
};

const purgeOldSynced = (q) => {
  const cutoff = Date.now() - SYNCED_TTL_MS;
  return q.filter(
    (x) => !(x.state === "synced" && x.syncedAt && new Date(x.syncedAt).getTime() < cutoff),
  );
};

// ── queue drain loop (single-flight) ──────────────────────────────────────
let processing = false;

const processQueue = async () => {
  if (processing) return;
  processing = true;
  try {
    let progressed = true;
    while (progressed) {
      progressed = false;
      const q = load();
      for (const item of q) {
        const changed = await attemptItem(item, q);
        if (changed) progressed = true;
      }
      const cleaned = purgeOldSynced(load());
      if (cleaned.length !== load().length) save(cleaned);
    }
  } finally {
    processing = false;
  }
};

setInterval(processQueue, 4000);
if (typeof window !== "undefined") {
  window.addEventListener("online", () => processQueue());
}

// ── public API ────────────────────────────────────────────────────────────
const enqueue = (item) => {
  const q = load();
  q.push(item);
  save(q);
  processQueue();
  return item.id;
};

export const enqueueComplete = (task_id, { outcome = "done", payload_actual = {}, notes } = {}) => {
  const client_completion_id = newClientCompletionId();
  return enqueue({
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
};

export const enqueueSkip = (task_id, { refused = false, reason, notes } = {}) => {
  const client_completion_id = newClientCompletionId();
  return enqueue({
    id: client_completion_id,
    task_id,
    kind: "single",
    action: "skip",
    state: "queued",
    attempts: 0,
    enqueuedAt: new Date().toISOString(),
    body: { client_completion_id, refused, reason: reason || null, notes: notes || null },
  });
};

export const enqueueBulkComplete = (task_ids, { shared_note } = {}) => {
  if (!task_ids.length) return null;
  const items = task_ids.map((tid) => ({
    task_id: tid,
    client_completion_id: newClientCompletionId(),
    outcome: "done",
    completed_at: new Date().toISOString(),
  }));
  const id = newClientCompletionId();
  return enqueue({
    id,
    kind: "bulk",
    state: "queued",
    attempts: 0,
    enqueuedAt: new Date().toISOString(),
    body: { items, shared_note: shared_note || null },
    task_ids,
  });
};

export const getPendingForTask = (task_id) =>
  load().filter(
    (x) =>
      x.state !== "synced" &&
      (x.task_id === task_id || (x.kind === "bulk" && x.task_ids?.includes(task_id))),
  );

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
