import React from "react";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Check, UtensilsCrossed, Clock, AlertTriangle, CheckCircle2 } from "lucide-react";
import { fmtTime } from "../lib/api";
import { useEngineTasksToday, horseLabel, bucketByTimeOfDay } from "../lib/engineTasks";

const FeedRow = ({ task, horses, onComplete, onSkip, syncState }) => {
  const done = task.status === "completed" || task.status === "skipped";
  const payload = task.payload || {};
  const detail = [payload.feed_type, payload.amount && `${payload.amount} ${payload.unit || ""}`]
    .filter(Boolean).join(" · ");

  return (
    <div data-testid={`feed-row-${task.id}`} className="py-3 hairline">
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
              onClick={() => onSkip(task, { reason: "Skipped from Feed Room" })}
              data-testid={`feed-skip-${task.id}`}
              className="hidden sm:inline-flex items-center justify-center w-8 h-8 rounded-lg text-equine-clay hover:bg-equine-clay/10 transition-colors"
              aria-label="Skip"
            >
              ×
            </button>
            <button
              data-testid={`feed-complete-${task.id}`}
              onClick={() => onComplete(task)}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-equine-navy text-white text-[12px] hover:bg-equine-navyLift active:scale-95 transition-all"
            >
              <Check className="w-3.5 h-3.5" strokeWidth={2.5} /> Mark
            </button>
          </div>
        )}
      </div>
      {payload.supplements?.length > 0 && (
        <div className="ml-9 mt-1.5 text-[11.5px] text-equine-amber inline-flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3" /> {payload.supplements.join(", ")}
        </div>
      )}
    </div>
  );
};

export default function Feed() {
  const { tasks, horses, loading, complete, skip, syncStateForTask } =
    useEngineTasksToday(["feed"]);
  const buckets = bucketByTimeOfDay(tasks);
  const done = tasks.filter((t) => t.status === "completed" || t.status === "skipped").length;

  const groups = [
    { key: "morning", label: "Morning", items: buckets.morning },
    { key: "midday", label: "Midday", items: buckets.midday },
    { key: "evening", label: "Evening", items: buckets.evening },
  ];

  return (
    <div data-testid="feed-page" className="pb-20 lg:pb-8">
      <PageHeader
        eyebrow="Feed Room"
        title="Today's Feeding"
        subtitle="Every meal flows through the unified care engine. Tap to sign off — completions sync to each horse's timeline."
        action={
          <StatusPill tone={done === tasks.length && tasks.length ? "success" : "info"}>
            {done} of {tasks.length} completed
          </StatusPill>
        }
      />

      {loading && tasks.length === 0 ? (
        <div className="py-16 text-center text-equine-inkSoft text-[13px]">Loading today's rations…</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {groups.map((g) => (
            <Card key={g.key} data-testid={`feed-group-${g.key}`}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display text-2xl capitalize text-equine-ink">{g.label}</h2>
                <UtensilsCrossed strokeWidth={1.4} className="w-5 h-5 text-equine-saddle" />
              </div>
              {g.items.length === 0 ? (
                <div className="text-[12.5px] text-equine-inkSoft italic py-3">No meals scheduled.</div>
              ) : (
                g.items.map((t) => (
                  <FeedRow
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
          ))}
        </div>
      )}
    </div>
  );
}
