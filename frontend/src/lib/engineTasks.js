/**
 * Shared hook + presenters for engine-backed task views.
 * Used by Feed.jsx, Medications.jsx, and any future category-specific page.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import {
  enqueueComplete, enqueueSkip, subscribeSyncState,
} from "./taskSync";

// Map a sync-queue snapshot to `{ task_id: state }` and the count of synced items.
const summarizeQueue = (q) => {
  const map = {};
  let syncedCount = 0;
  for (const item of q) {
    if (item.state === "synced") { syncedCount += 1; continue; }
    const ids = item.kind === "bulk" ? (item.task_ids || []) : [item.task_id];
    for (const tid of ids) {
      if (item.state === "failed") map[tid] = "failed";
      else if (item.state === "syncing" && map[tid] !== "failed") map[tid] = "syncing";
      else if (!map[tid]) map[tid] = "queued";
    }
  }
  return { map, syncedCount };
};

const todayBounds = () => {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 1);
  return { start: start.toISOString(), end: end.toISOString() };
};

/** Window into engine tasks for one or more categories on a given date. */
export const useEngineTasksToday = (categories) => {
  const cats = useMemo(
    () => (Array.isArray(categories) ? categories : [categories]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [Array.isArray(categories) ? categories.join(",") : categories],
  );

  const [tasks, setTasks] = useState([]);
  const [horses, setHorses] = useState({});
  const [optimistic, setOptimistic] = useState({});
  const [queueState, setQueueState] = useState({});
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const { start, end } = todayBounds();
      const fetched = await Promise.all(
        cats.map((c) =>
          api.get(`/tasks?category=${c}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`)
        ),
      );
      const merged = [];
      fetched.forEach((r) => merged.push(...(r.data.items || [])));
      merged.sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
      setTasks(merged);
      const hr = await api.get("/horses");
      const map = {};
      (hr.data || []).forEach((h) => { map[h.id] = h; });
      setHorses(map);
    } finally {
      setLoading(false);
    }
  }, [cats]);

  useEffect(() => { reload(); }, [reload]);

  // Listen for queue completions and refresh data when something syncs.
  useEffect(() => {
    let lastSynced = 0;
    return subscribeSyncState((q) => {
      const { map, syncedCount } = summarizeQueue(q);
      setQueueState(map);
      if (syncedCount > lastSynced) {
        lastSynced = syncedCount;
        reload();
      }
    });
  }, [reload]);

  const decoratedTasks = useMemo(() => {
    return tasks.map((t) => {
      const override = optimistic[t.id];
      return override ? { ...t, status: override } : t;
    });
  }, [tasks, optimistic]);

  const complete = useCallback((task, opts = {}) => {
    setOptimistic((s) => ({ ...s, [task.id]: "completed" }));
    enqueueComplete(task.id, opts);
  }, []);

  const skip = useCallback((task, opts = {}) => {
    setOptimistic((s) => ({ ...s, [task.id]: "skipped" }));
    enqueueSkip(task.id, opts);
  }, []);

  const syncStateForTask = useCallback((id) => queueState[id], [queueState]);

  return {
    tasks: decoratedTasks,
    horses,
    loading,
    complete,
    skip,
    reload,
    syncStateForTask,
  };
};

export const horseLabel = (task, horses) => {
  const names = (task.linked_horse_ids || [])
    .map((id) => horses[id]?.name)
    .filter(Boolean);
  if (!names.length) return "All horses";
  if (names.length <= 2) return names.join(" · ");
  return `${names.slice(0, 2).join(" · ")} +${names.length - 2}`;
};

export const bucketByTimeOfDay = (tasks) => {
  const morning = [];
  const midday = [];
  const evening = [];
  for (const t of tasks) {
    const h = new Date(t.scheduled_at).getHours();
    if (h < 11) morning.push(t);
    else if (h < 15) midday.push(t);
    else evening.push(t);
  }
  return { morning, midday, evening };
};
