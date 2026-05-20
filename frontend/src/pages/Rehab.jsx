import React from "react";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import {
  Check, Heart, Clock, CheckCircle2, ChevronRight,
} from "lucide-react";
import { fmtTime } from "../lib/api";
import { useEngineTasksToday, horseLabel } from "../lib/engineTasks";
import { Link } from "react-router-dom";

/**
 * Rehab — a specialized operational view over the unified Task Engine.
 * Reads `category=rehab` tasks via the shared hook; no parallel scheduling
 * logic. Completions flow through the same offline-capable taskSync queue.
 */
const RehabRow = ({ task, horses, onComplete, onSkip, syncState }) => {
  const done = task.status === "completed" || task.status === "skipped";
  const payload = task.payload || {};
  const detail = [
    payload.activity,
    payload.duration_min && `${payload.duration_min} min`,
    payload.surface,
  ].filter(Boolean).join(" · ");

  return (
    <div data-testid={`rehab-row-${task.id}`} className="py-3 hairline">
      <div className="flex items-center gap-3">
        <Clock className="w-3.5 h-3.5 text-equine-inkSoft flex-shrink-0" />
        <div className="font-mono text-[13px] text-equine-inkMuted w-16 flex-shrink-0">
          {fmtTime(task.scheduled_at)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] text-equine-ink truncate">{horseLabel(task, horses)}</div>
          <div className="text-[12px] text-equine-inkMuted truncate">
            {task.title}{detail && ` — ${detail}`}
          </div>
        </div>
        {syncState && (
          <span className={`w-1.5 h-1.5 rounded-full ${
            syncState === "failed" ? "bg-equine-clay" : "bg-equine-brassLight animate-pulse"
          }`} />
        )}
        {done ? (
          <CheckCircle2 className="w-5 h-5 text-equine-sage flex-shrink-0" />
        ) : (
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              onClick={() => onSkip(task, { reason: "Skipped from Rehab" })}
              data-testid={`rehab-skip-${task.id}`}
              className="hidden sm:inline-flex items-center justify-center w-8 h-8 rounded-lg text-equine-clay hover:bg-equine-clay/10 transition-colors"
              aria-label="Skip"
            >
              ×
            </button>
            <button
              data-testid={`rehab-complete-${task.id}`}
              onClick={() => onComplete(task)}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-equine-navy text-white text-[12px] hover:bg-equine-navyLift active:scale-95 transition-all"
            >
              <Check className="w-3.5 h-3.5" strokeWidth={2.5} /> Log
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default function Rehab() {
  const { tasks, horses, loading, complete, skip, syncStateForTask } =
    useEngineTasksToday(["rehab"]);
  const done = tasks.filter((t) => t.status === "completed" || t.status === "skipped").length;

  return (
    <div data-testid="rehab-page" className="pb-20 lg:pb-8">
      <PageHeader
        eyebrow="Stall Rest & Rehab"
        title="Today's Rehab Plan"
        subtitle="Hand-walking, icing and rehab sessions for every horse on restricted exercise. Every log flows through the unified care engine."
        action={
          <Link
            to="/today"
            data-testid="rehab-open-today"
            className="hidden lg:inline-flex items-center gap-1 text-[12.5px] text-equine-inkMuted hover:text-equine-ink"
          >
            Open Today <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      <Card className="mb-6 flex items-center justify-between flex-wrap gap-3" data-testid="rehab-summary">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
            <Heart strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
          </div>
          <div>
            <div className="text-[12px] uppercase tracking-[0.2em] text-equine-inkSoft">Today</div>
            <div className="text-equine-ink text-[15px]">
              {done} of {tasks.length} sessions logged
            </div>
          </div>
        </div>
        {tasks.length === 0 && !loading && (
          <StatusPill tone="neutral">No rehab horses today</StatusPill>
        )}
        {tasks.length > 0 && done === tasks.length && (
          <StatusPill tone="success" dot>All sessions logged</StatusPill>
        )}
      </Card>

      <Card>
        {loading ? (
          <div className="text-equine-inkSoft text-[13px] py-6 text-center">
            Loading rehab plan…
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-equine-inkSoft text-[13px] py-8 text-center">
            No rehab sessions scheduled for today. When a horse is placed on stall rest,
            sessions will appear here automatically.
          </div>
        ) : (
          tasks.map((t) => (
            <RehabRow
              key={t.id}
              task={t}
              horses={horses}
              onComplete={complete}
              onSkip={skip}
              syncState={syncStateForTask(t.id)}
            />
          ))
        )}
      </Card>
    </div>
  );
}
