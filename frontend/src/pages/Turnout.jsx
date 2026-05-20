import React from "react";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import {
  Check, Trees, Clock, CheckCircle2, Sunrise, Sunset, ChevronRight,
} from "lucide-react";
import { fmtTime } from "../lib/api";
import { useEngineTasksToday, horseLabel } from "../lib/engineTasks";
import { Link } from "react-router-dom";

/**
 * Turnout — operational view over turnout_out + turnout_in engine tasks.
 * Reuses the unified Task Engine via the shared hook. No parallel state.
 */
const TurnoutRow = ({ task, horses, onComplete, onSkip, syncState }) => {
  const done = task.status === "completed" || task.status === "skipped";
  const payload = task.payload || {};
  const detail = [payload.paddock, payload.group, payload.weather_note]
    .filter(Boolean).join(" · ");
  const isOut = task.category === "turnout_out";

  return (
    <div data-testid={`turnout-row-${task.id}`} className="py-3 hairline">
      <div className="flex items-center gap-3">
        {isOut
          ? <Sunrise className="w-3.5 h-3.5 text-equine-amber flex-shrink-0" />
          : <Sunset className="w-3.5 h-3.5 text-equine-inkSoft flex-shrink-0" />}
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
              onClick={() => onSkip(task, { reason: "Skipped from Turnout" })}
              data-testid={`turnout-skip-${task.id}`}
              className="hidden sm:inline-flex items-center justify-center w-8 h-8 rounded-lg text-equine-clay hover:bg-equine-clay/10 transition-colors"
              aria-label="Skip"
            >
              ×
            </button>
            <button
              data-testid={`turnout-complete-${task.id}`}
              onClick={() => onComplete(task)}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-equine-navy text-white text-[12px] hover:bg-equine-navyLift active:scale-95 transition-all"
            >
              <Check className="w-3.5 h-3.5" strokeWidth={2.5} /> {isOut ? "Out" : "In"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default function Turnout() {
  const { tasks, horses, loading, complete, skip, syncStateForTask } =
    useEngineTasksToday(["turnout_out", "turnout_in"]);
  const out = tasks.filter((t) => t.category === "turnout_out");
  const inn = tasks.filter((t) => t.category === "turnout_in");
  const done = tasks.filter((t) => t.status === "completed" || t.status === "skipped").length;

  const groups = [
    { key: "out", label: "Turnout out", items: out, icon: Sunrise },
    { key: "in", label: "Bring in", items: inn, icon: Sunset },
  ];

  return (
    <div data-testid="turnout-page" className="pb-20 lg:pb-8">
      <PageHeader
        eyebrow="Turnout & Pastures"
        title="Today's Turnout"
        subtitle="Morning turn-outs and evening bring-ins, grouped naturally. Every move flows through the unified care engine."
        action={
          <Link
            to="/today"
            data-testid="turnout-open-today"
            className="hidden lg:inline-flex items-center gap-1 text-[12.5px] text-equine-inkMuted hover:text-equine-ink"
          >
            Open Today <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        }
      />

      <Card className="mb-6 flex items-center justify-between flex-wrap gap-3" data-testid="turnout-summary">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
            <Trees strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
          </div>
          <div>
            <div className="text-[12px] uppercase tracking-[0.2em] text-equine-inkSoft">Today</div>
            <div className="text-equine-ink text-[15px]">
              {done} of {tasks.length} moves logged
            </div>
          </div>
        </div>
        {tasks.length > 0 && done === tasks.length && (
          <StatusPill tone="success" dot>All horses settled</StatusPill>
        )}
      </Card>

      {loading ? (
        <Card>
          <div className="text-equine-inkSoft text-[13px] py-6 text-center">
            Loading turnout plan…
          </div>
        </Card>
      ) : tasks.length === 0 ? (
        <Card>
          <div className="text-equine-inkSoft text-[13px] py-8 text-center">
            No turnout moves scheduled for today.
          </div>
        </Card>
      ) : (
        groups.map((g) => {
          if (g.items.length === 0) return null;
          const Icon = g.icon;
          return (
            <Card key={g.key} className="mb-4" data-testid={`turnout-group-${g.key}`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className="w-3.5 h-3.5 text-equine-inkSoft" />
                <div className="text-[11px] uppercase tracking-[0.2em] text-equine-inkSoft">
                  {g.label} · {g.items.length}
                </div>
              </div>
              {g.items.map((t) => (
                <TurnoutRow
                  key={t.id}
                  task={t}
                  horses={horses}
                  onComplete={complete}
                  onSkip={skip}
                  syncState={syncStateForTask(t.id)}
                />
              ))}
            </Card>
          );
        })
      )}
    </div>
  );
}
