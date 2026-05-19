import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { api, fmtTime } from "../lib/api";
import {
  enqueueComplete, enqueueSkip, enqueueBulkComplete,
  subscribeSyncState, retryFailed,
} from "../lib/taskSync";
import { PageHeader, Card, StatusPill, SectionEyebrow, Empty } from "../components/Primitives";
import {
  Check, X, AlertTriangle, Clock, Sparkles, ChevronDown, ChevronUp,
  CheckCircle2, CloudOff, RotateCw, Filter, Layers, MoreHorizontal,
  UtensilsCrossed, Pill, Trees, BedDouble, Hammer, Stethoscope, Activity, Circle,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

const CATEGORY_META = {
  feed:        { label: "Feed",       icon: UtensilsCrossed, accent: "saddle" },
  medication:  { label: "Medication", icon: Pill,            accent: "critical" },
  turnout_out: { label: "Turnout",    icon: Trees,           accent: "info" },
  turnout_in:  { label: "Bring-in",   icon: Trees,           accent: "info" },
  stall_clean: { label: "Stall",      icon: BedDouble,       accent: "neutral" },
  farrier:     { label: "Farrier",    icon: Hammer,          accent: "brass" },
  vet:         { label: "Vet",        icon: Stethoscope,     accent: "warning" },
  rehab:       { label: "Rehab",      icon: Activity,        accent: "brass" },
  custom:      { label: "Task",       icon: Circle,          accent: "neutral" },
};

const GROUP_META = {
  overdue_critical: { label: "Overdue · Critical",       tone: "critical",  always: true },
  due_now:          { label: "Due now",                  tone: "warning",   always: true },
  upcoming_next_4h: { label: "Upcoming · next 4 hours",  tone: "info",      always: true },
  later_today:      { label: "Later today",              tone: "neutral",   collapsed: true },
  completed_today:  { label: "Completed today",          tone: "success",   collapsed: true },
  informational:    { label: "Informational",            tone: "neutral",   collapsed: true },
};

const GROUP_ORDER = ["overdue_critical", "due_now", "upcoming_next_4h", "later_today", "completed_today", "informational"];

// ────────────────────────────────────────────────────────────────────────────
// Sync indicator
// ────────────────────────────────────────────────────────────────────────────
const SyncDot = ({ state }) => {
  const map = {
    synced:  { cls: "bg-equine-sage", label: "Synced", pulse: false },
    queued:  { cls: "bg-equine-brassLight", label: "Queued", pulse: true },
    syncing: { cls: "bg-equine-brassLight", label: "Syncing", pulse: true },
    retry:   { cls: "bg-equine-amber", label: "Retrying", pulse: true },
    failed:  { cls: "bg-equine-clay", label: "Sync failed", pulse: false, ring: true },
  };
  const it = map[state] || map.synced;
  return (
    <span className="inline-flex items-center gap-1.5" title={it.label} data-testid={`sync-dot-${state}`}>
      <span className={`relative inline-flex w-1.5 h-1.5 rounded-full ${it.cls}`}>
        {it.pulse && <span className={`absolute inset-0 rounded-full ${it.cls} animate-ping opacity-50`} />}
        {it.ring && <span className="absolute -inset-1 rounded-full ring-1 ring-equine-clay/50" />}
      </span>
    </span>
  );
};

const SyncHeaderBadge = () => {
  const [q, setQ] = useState([]);
  useEffect(() => subscribeSyncState(setQ), []);
  const pending = q.filter((x) => x.state === "queued" || x.state === "syncing").length;
  const failed  = q.filter((x) => x.state === "failed").length;
  if (pending === 0 && failed === 0) return null;
  return (
    <div
      data-testid="sync-header-badge"
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11.5px] tracking-wide ${
        failed > 0
          ? "bg-equine-clay/10 border-equine-clay/30 text-equine-clay"
          : "bg-equine-brass/10 border-equine-brass/30 text-equine-navy"
      }`}
    >
      {failed > 0 ? <CloudOff className="w-3.5 h-3.5" /> : <RotateCw className="w-3.5 h-3.5 animate-spin" />}
      <span>
        {failed > 0
          ? `${failed} sync issue${failed > 1 ? "s" : ""}`
          : `Syncing ${pending}…`}
      </span>
      {failed > 0 && (
        <button
          data-testid="sync-retry-now"
          onClick={() => retryFailed()}
          className="ml-1 underline underline-offset-2 hover:text-equine-ink transition-colors"
        >
          Retry now
        </button>
      )}
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// TaskCard — swipe to complete on touch, button on desktop
// ────────────────────────────────────────────────────────────────────────────
const TaskCard = ({ task, horses, onComplete, onSkip, onSelectToggle, selected, bulkMode, syncStateForTask }) => {
  const meta = CATEGORY_META[task.category] || CATEGORY_META.custom;
  const Icon = meta.icon;
  const horseNames = (task.linked_horse_ids || []).map((id) => horses[id]?.name).filter(Boolean);
  const horsesLabel = horseNames.length === 0 ? "All horses"
    : horseNames.length <= 2 ? horseNames.join(" · ")
    : `${horseNames.slice(0, 2).join(" · ")} +${horseNames.length - 2}`;

  // touch swipe state
  const [dx, setDx] = useState(0);
  const startRef = useRef({ x: 0, t: 0, active: false });
  const completed = task.status === "completed" || task.status === "skipped";

  const onTouchStart = (e) => {
    if (completed || bulkMode) return;
    const t = e.touches[0];
    startRef.current = { x: t.clientX, t: Date.now(), active: true };
  };
  const onTouchMove = (e) => {
    if (!startRef.current.active) return;
    const t = e.touches[0];
    const delta = t.clientX - startRef.current.x;
    // only allow horizontal swipes within reasonable bounds
    setDx(Math.max(-100, Math.min(160, delta)));
  };
  const onTouchEnd = () => {
    if (!startRef.current.active) return;
    startRef.current.active = false;
    if (dx > 90) {
      setDx(180);
      setTimeout(() => { setDx(0); onComplete(task); }, 180);
    } else if (dx < -70) {
      setDx(-120);
      setTimeout(() => { setDx(0); onSkip(task); }, 180);
    } else {
      setDx(0);
    }
  };

  const swipeOpacity = Math.min(1, Math.abs(dx) / 90);
  const sync = syncStateForTask(task.id);

  return (
    <div className="relative" data-testid={`task-row-${task.id}`}>
      {/* swipe-action layer */}
      {dx > 4 && (
        <div className="absolute inset-y-0 left-0 right-0 rounded-2xl bg-equine-sage/15 flex items-center pl-5 pointer-events-none"
             style={{ opacity: swipeOpacity }}>
          <Check strokeWidth={2} className="w-5 h-5 text-equine-sage" />
          <span className="ml-2 text-[12px] text-equine-sage font-medium tracking-wide">Complete</span>
        </div>
      )}
      {dx < -4 && (
        <div className="absolute inset-y-0 left-0 right-0 rounded-2xl bg-equine-clay/15 flex items-center justify-end pr-5 pointer-events-none"
             style={{ opacity: swipeOpacity }}>
          <span className="mr-2 text-[12px] text-equine-clay font-medium tracking-wide">Skip</span>
          <X strokeWidth={2} className="w-5 h-5 text-equine-clay" />
        </div>
      )}

      <div
        className={`relative bg-equine-card border border-equine-hairline rounded-2xl px-4 py-3.5 transition-transform duration-150 ease-out
          ${completed ? "opacity-60" : ""}
          ${selected ? "ring-2 ring-equine-brassLight" : ""}`}
        style={{ transform: `translateX(${dx}px)` }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <div className="flex items-center gap-3.5">
          {bulkMode ? (
            <button
              onClick={() => onSelectToggle(task.id)}
              data-testid={`bulk-toggle-${task.id}`}
              className={`flex-shrink-0 w-6 h-6 rounded-md border-2 flex items-center justify-center transition-colors
                ${selected ? "bg-equine-navy border-equine-navy text-white" : "border-equine-graphite hover:border-equine-navy"}`}
              aria-label={selected ? "Deselect" : "Select"}
            >
              {selected && <Check className="w-3.5 h-3.5" strokeWidth={3} />}
            </button>
          ) : (
            <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center flex-shrink-0">
              <Icon strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <div className="text-[14px] text-equine-ink font-medium truncate">{task.title}</div>
              {task.priority === "critical" && (
                <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.18em] text-equine-clay font-semibold">
                  <AlertTriangle className="w-3 h-3" /> Critical
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-[12px] text-equine-inkMuted flex-wrap">
              <Clock className="w-3 h-3" />
              <span>{fmtTime(task.scheduled_at)}</span>
              <span className="text-equine-inkSoft">·</span>
              <span className="truncate">{horsesLabel}</span>
              {task.assignee_role && (
                <>
                  <span className="text-equine-inkSoft">·</span>
                  <span className="capitalize">{task.assignee_role.replace(/_/g, " ")}</span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            {sync && <SyncDot state={sync} />}
            {completed ? (
              <CheckCircle2 className="w-5 h-5 text-equine-sage" />
            ) : !bulkMode ? (
              <>
                <button
                  onClick={() => onSkip(task)}
                  data-testid={`skip-btn-${task.id}`}
                  className="hidden sm:inline-flex items-center justify-center w-9 h-9 rounded-xl text-equine-clay hover:bg-equine-clay/10 transition-colors"
                  aria-label="Skip task"
                >
                  <X className="w-4 h-4" strokeWidth={2} />
                </button>
                <button
                  onClick={() => onComplete(task)}
                  data-testid={`complete-btn-${task.id}`}
                  className="inline-flex items-center justify-center w-11 h-11 rounded-xl bg-equine-navy text-white shadow-sm hover:bg-equine-navyLift active:scale-95 transition-all"
                  aria-label="Complete task"
                >
                  <Check className="w-5 h-5" strokeWidth={2.2} />
                </button>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// Group section
// ────────────────────────────────────────────────────────────────────────────
const Group = ({ groupKey, items, horses, onComplete, onSkip, onSelectToggle, selectedSet, bulkMode, syncStateForTask }) => {
  const meta = GROUP_META[groupKey];
  const [open, setOpen] = useState(!meta.collapsed);
  if (!items.length && !meta.always) return null;
  return (
    <section className="mb-7" data-testid={`group-${groupKey}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 mb-3 group"
      >
        <div className="flex items-center gap-2.5">
          <StatusPill tone={meta.tone} dot>{meta.label}</StatusPill>
          <span className="text-[12px] text-equine-inkMuted">{items.length}</span>
        </div>
        <div className="flex-1 h-px bg-equine-hairline group-hover:bg-equine-graphite/60 transition-colors" />
        {meta.collapsed && (open ? <ChevronUp className="w-4 h-4 text-equine-inkSoft" /> : <ChevronDown className="w-4 h-4 text-equine-inkSoft" />)}
      </button>
      {open && (
        items.length === 0 ? (
          <div className="text-[12.5px] text-equine-inkSoft px-1 py-2 italic">Nothing here. A quiet stretch.</div>
        ) : (
          <div className="space-y-2.5">
            {items.map((t) => (
              <TaskCard
                key={t.id}
                task={t}
                horses={horses}
                onComplete={onComplete}
                onSkip={onSkip}
                onSelectToggle={onSelectToggle}
                selected={selectedSet.has(t.id)}
                bulkMode={bulkMode}
                syncStateForTask={syncStateForTask}
              />
            ))}
          </div>
        )
      )}
    </section>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// Today page
// ────────────────────────────────────────────────────────────────────────────
export default function Today() {
  const [data, setData] = useState(null);
  const [horses, setHorses] = useState({});
  const [filter, setFilter] = useState(null);
  const [bulkMode, setBulkMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  // optimistic overlay: { [task_id]: 'completed' | 'skipped' }
  const [optimistic, setOptimistic] = useState({});
  // sync state map: { [task_id]: 'queued' | 'syncing' | 'failed' }
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
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  // periodic light refresh — no jank
  useEffect(() => {
    const id = setInterval(reload, 60_000);
    return () => clearInterval(id);
  }, [reload]);

  // subscribe to queue state for sync dots & to detect when items synced (then reload)
  useEffect(() => {
    let lastSyncedCount = 0;
    return subscribeSyncState((q) => {
      const map = {};
      let synced = 0;
      for (const item of q) {
        if (item.state === "synced") { synced++; continue; }
        const ids = item.kind === "bulk" ? (item.task_ids || []) : [item.task_id];
        for (const tid of ids) {
          // failed > syncing > queued
          if (item.state === "failed") map[tid] = "failed";
          else if (item.state === "syncing") map[tid] = map[tid] === "failed" ? "failed" : "syncing";
          else if (!map[tid]) map[tid] = "queued";
        }
      }
      setQueueState(map);
      // if any newly synced, refresh today data
      if (synced > lastSyncedCount) {
        lastSyncedCount = synced;
        reload();
      }
    });
  }, [reload]);

  const syncStateForTask = useCallback((id) => queueState[id], [queueState]);

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

  // ── grouping + filtering with optimistic overlay ────────────────────────
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
        // move to completed bucket if optimistically completed/skipped
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
    ? (grouped.overdue_critical.length + grouped.due_now.length + grouped.upcoming_next_4h.length + grouped.later_today.length)
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
        action={<SyncHeaderBadge />}
      />

      {/* Filter / bulk toolbar */}
      <div className="sticky top-[64px] z-10 -mx-5 lg:mx-0 px-5 lg:px-0 py-3 mb-5 bg-equine-black/85 backdrop-blur-md border-b border-equine-hairline">
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-luxe pb-1">
          <button
            data-testid="filter-chip-all"
            onClick={() => setFilter(null)}
            className={`shrink-0 px-3 py-1.5 rounded-full text-[12px] tracking-wide transition-colors border ${
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
                className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] tracking-wide transition-colors border ${
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
              className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] tracking-wide border transition-colors ${
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
        <div className="grid place-items-center py-24 text-equine-inkSoft text-[13px]">Composing today…</div>
      ) : grouped ? (
        <>
          {GROUP_ORDER.map((k) => (
            <Group
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
