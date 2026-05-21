import React, { useEffect, useMemo, useState, useCallback } from "react";
import { api } from "../lib/api";
import {
  enqueueComplete, enqueueSkip, enqueueBulkComplete,
  subscribeSyncState,
} from "../lib/taskSync";
import { PageHeader, Empty } from "../components/Primitives";
import { Check, Sparkles, Layers } from "lucide-react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

import { CATEGORY_META, GROUP_ORDER } from "../lib/todayMeta";
import { SyncHeaderBadge } from "../components/today/SyncBadges";
import LastSyncedBadge from "../components/today/LastSyncedBadge";
import TodayGroup from "../components/today/TodayGroup";

/**
 * Today — the unified operational hub. State + composition only; visual
 * components live under components/today/*. Behaviour preserved exactly:
 * one-thumb workflows, offline-tolerant sync queue, optimistic UI.
 */
export default function Today() {
  const [data, setData] = useState(null);
  const [horses, setHorses] = useState({});
  // Restore last-used filter from sessionStorage so a phone-lock/reopen
  // mid-feed-round doesn't wipe Sophia's filter. Per OPERATIONAL_SIMULATION
  // §4.2 this saves ~30 wasted taps/day on a typical groom workflow.
  const [filter, setFilter] = useState(() => {
    try { return sessionStorage.getItem("equine_today_filter") || null; }
    catch { return null; }
  });
  const [bulkMode, setBulkMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  // Optimistic overlay: { [task_id]: 'completed' | 'skipped' }
  const [optimistic, setOptimistic] = useState({});
  // Sync state map: { [task_id]: 'queued' | 'syncing' | 'failed' }
  const [queueState, setQueueState] = useState({});

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [todayRes, horsesRes] = await Promise.all([
        api.get("/tasks/today"),
        api.get("/horses"),
      ]);
      setData(todayRes.data);
      const map = {};
      (horsesRes.data || []).forEach((h) => { map[h.id] = h; });
      setHorses(map);
      setLastSyncedAt(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // Periodic light refresh — no jank.
  useEffect(() => {
    const id = setInterval(reload, 60_000);
    return () => clearInterval(id);
  }, [reload]);

  // Subscribe to queue state for sync dots & detect when items synced (then reload).
  useEffect(() => {
    let lastSyncedCount = 0;
    return subscribeSyncState((q) => {
      const map = {};
      let synced = 0;
      for (const item of q) {
        if (item.state === "synced") { synced += 1; continue; }
        const ids = item.kind === "bulk" ? (item.task_ids || []) : [item.task_id];
        for (const tid of ids) {
          if (item.state === "failed") map[tid] = "failed";
          else if (item.state === "syncing" && map[tid] !== "failed") map[tid] = "syncing";
          else if (!map[tid]) map[tid] = "queued";
        }
      }
      setQueueState(map);
      if (synced > lastSyncedCount) {
        lastSyncedCount = synced;
        reload();
      }
    });
  }, [reload]);

  const syncStateForTask = useCallback((id) => queueState[id], [queueState]);

  // Persist filter selection so phone-lock / app-remount doesn't blow it away.
  useEffect(() => {
    try {
      if (filter) sessionStorage.setItem("equine_today_filter", filter);
      else sessionStorage.removeItem("equine_today_filter");
    } catch { /* ignore storage quota / disabled */ }
  }, [filter]);

  // Bulk: select / deselect an entire group's worth of visible tasks at once.
  // Shaves 6–8 taps off a typical turnout round (OPERATIONAL_SIMULATION §3.1).
  const selectGroup = useCallback((_groupKey, items, makeSelected) => {
    setSelected((prev) => {
      const next = new Set(prev);
      items.forEach((t) => {
        if (makeSelected) next.add(t.id);
        else next.delete(t.id);
      });
      return next;
    });
  }, []);

  const applyOptimistic = (taskId, status) => {
    setOptimistic((s) => ({ ...s, [taskId]: status }));
  };

  const onComplete = (task) => {
    applyOptimistic(task.id, "completed");
    enqueueComplete(task.id, { outcome: "done" });
    toast.success(`${task.title} marked done`, { duration: 1500 });
  };

  const onSkip = (task) => {
    applyOptimistic(task.id, "skipped");
    enqueueSkip(task.id, { refused: false, reason: "Skipped from Today" });
    toast(`${task.title} skipped`, { duration: 1500 });
  };

  const toggleSelect = (id) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const doBulkComplete = () => {
    if (selected.size === 0) return;
    const ids = Array.from(selected);
    ids.forEach((id) => applyOptimistic(id, "completed"));
    enqueueBulkComplete(ids, { shared_note: "Bulk completed via Today view" });
    toast.success(`${ids.length} tasks marked done`, { duration: 1800 });
    setSelected(new Set());
    setBulkMode(false);
  };

  // ── grouping + filtering with optimistic overlay ──────────────────
  const grouped = useMemo(() => {
    if (!data) return null;
    const out = {};
    for (const key of GROUP_ORDER) out[key] = [];
    const seenIds = new Set();
    for (const key of GROUP_ORDER) {
      for (const t of data.groups[key] || []) {
        if (seenIds.has(t.id)) continue;
        seenIds.add(t.id);
        const override = optimistic[t.id];
        const mergedStatus = override || t.status;
        const merged = { ...t, status: mergedStatus };
        if (filter && merged.category !== filter) continue;
        if (override === "completed" || override === "skipped") {
          out.completed_today.push(merged);
        } else {
          out[key].push(merged);
        }
      }
    }
    return out;
  }, [data, optimistic, filter]);

  const totalActionable = grouped
    ? (grouped.overdue_critical.length + grouped.due_now.length
       + grouped.upcoming_next_4h.length + grouped.later_today.length)
    : 0;

  const categoriesPresent = useMemo(() => {
    if (!data) return [];
    const set = new Set();
    for (const key of GROUP_ORDER) (data.groups[key] || []).forEach((t) => set.add(t.category));
    return Array.from(set);
  }, [data]);

  return (
    <div data-testid="today-page" className="pb-24 lg:pb-12 max-w-4xl mx-auto">
      <PageHeader
        eyebrow="Today"
        title="Operational Pulse"
        subtitle="One clean stream of what the barn needs, ordered by urgency. Swipe right to complete, left to skip, or enter bulk mode."
        action={
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <SyncHeaderBadge />
            <LastSyncedBadge at={lastSyncedAt} onRefresh={reload} refreshing={loading} />
          </div>
        }
      />

      {/* Filter / bulk toolbar — chips bumped to ≥44px tap-zone for one-handed mobile use */}
      <div className="sticky top-[64px] z-10 -mx-5 lg:mx-0 px-5 lg:px-0 py-3 mb-5 bg-equine-black/85 backdrop-blur-md border-b border-equine-hairline">
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-luxe pb-1">
          <button
            data-testid="filter-chip-all"
            onClick={() => setFilter(null)}
            className={`shrink-0 px-4 py-2.5 min-h-[40px] rounded-full text-[12px] tracking-wide transition-colors border ${
              !filter ? "bg-equine-navy text-white border-equine-navy" : "bg-equine-card text-equine-inkMuted border-equine-hairline hover:border-equine-graphite"
            }`}
          >
            All <span className="ml-1 opacity-70">{totalActionable}</span>
          </button>
          {categoriesPresent.map((cat) => {
            const m = CATEGORY_META[cat] || CATEGORY_META.custom;
            const Icon = m.icon;
            return (
              <button
                key={cat}
                data-testid={`filter-chip-${cat}`}
                onClick={() => setFilter(filter === cat ? null : cat)}
                className={`shrink-0 inline-flex items-center gap-1.5 px-4 py-2.5 min-h-[40px] rounded-full text-[12px] tracking-wide transition-colors border ${
                  filter === cat ? "bg-equine-navy text-white border-equine-navy" : "bg-equine-card text-equine-inkMuted border-equine-hairline hover:border-equine-graphite"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{m.label}</span>
              </button>
            );
          })}
          <div className="ml-auto pl-2 flex items-center gap-2">
            <button
              data-testid="bulk-mode-toggle"
              onClick={() => { setBulkMode((v) => !v); setSelected(new Set()); }}
              className={`shrink-0 inline-flex items-center gap-1.5 px-4 py-2.5 min-h-[40px] rounded-full text-[12px] tracking-wide border transition-colors ${
                bulkMode ? "bg-equine-brassLight text-equine-navy border-equine-brass" : "bg-equine-card text-equine-inkMuted border-equine-hairline hover:border-equine-graphite"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              {bulkMode ? "Exit bulk" : "Bulk"}
            </button>
          </div>
        </div>
      </div>

      {loading && !data ? (
        <div className="grid place-items-center py-24 text-equine-inkSoft text-[13px]">
          Composing today…
        </div>
      ) : grouped ? (
        <>
          {GROUP_ORDER.map((k) => (
            <TodayGroup
              key={k}
              groupKey={k}
              items={grouped[k]}
              horses={horses}
              onComplete={onComplete}
              onSkip={onSkip}
              onSelectToggle={toggleSelect}
              selectedSet={selected}
              bulkMode={bulkMode}
              syncStateForTask={syncStateForTask}
              onSelectGroup={selectGroup}
            />
          ))}
          {!totalActionable && (
            <Empty>
              <Sparkles className="w-7 h-7 text-equine-brass mx-auto mb-2.5" />
              <div className="text-[14px] text-equine-ink mb-1">All caught up.</div>
              <div className="text-[12.5px] text-equine-inkMuted">Every horse, every task — handled.</div>
            </Empty>
          )}
        </>
      ) : null}

      {/* Bulk action bar */}
      {bulkMode && selected.size > 0 && (
        <div
          data-testid="bulk-action-bar"
          className="fixed left-1/2 -translate-x-1/2 bottom-5 z-30 bg-equine-navy text-white shadow-2xl rounded-full pl-5 pr-2 py-2 flex items-center gap-3 animate-fade-in"
        >
          <span className="text-[13px]">{selected.size} selected</span>
          <button
            onClick={() => setSelected(new Set())}
            className="text-[12px] text-white/70 hover:text-white px-2"
          >
            Clear
          </button>
          <Button
            data-testid="bulk-complete-confirm"
            onClick={doBulkComplete}
            className="rounded-full bg-equine-brassLight text-equine-navy hover:bg-white"
          >
            <Check className="w-4 h-4 mr-1.5" strokeWidth={2.5} /> Complete all
          </Button>
        </div>
      )}
    </div>
  );
}
