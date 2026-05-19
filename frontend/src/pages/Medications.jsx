import React, { useEffect, useState } from "react";
import { api, fmtTime } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Pill, Check, CheckCircle2, AlertTriangle, Clock } from "lucide-react";
import { useEngineTasksToday, horseLabel } from "../lib/engineTasks";

const DoseRow = ({ task, horses, onComplete, onSkip, syncState }) => {
  const done = task.status === "completed" || task.status === "skipped";
  const payload = task.payload || {};
  const detail = [payload.med_name, payload.dose && `${payload.dose} ${payload.unit || ""}`, payload.route]
    .filter(Boolean).join(" · ");
  const refusedBefore = task.status === "skipped";

  return (
    <div data-testid={`med-dose-row-${task.id}`} className="flex items-center gap-3 py-3 hairline">
      <div className="font-display text-xl text-equine-saddle w-20 flex-shrink-0">
        <span className="inline-flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-equine-inkSoft" /> {fmtTime(task.scheduled_at)}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[14px] text-equine-ink truncate">{horseLabel(task, horses)} — {payload.med_name || task.title}</div>
        <div className="text-[12px] text-equine-inkMuted truncate">{detail}</div>
        {task.priority === "critical" && (
          <div className="text-[11px] text-equine-clay inline-flex items-center gap-1 mt-0.5">
            <AlertTriangle className="w-3 h-3" /> Critical
          </div>
        )}
      </div>
      {syncState && (
        <span className={`w-1.5 h-1.5 rounded-full ${
          syncState === "failed" ? "bg-equine-clay" : "bg-equine-brassLight animate-pulse"
        }`} />
      )}
      {done ? (
        <StatusPill tone={refusedBefore ? "warning" : "success"} dot>
          {refusedBefore ? "skipped" : "given"}
        </StatusPill>
      ) : (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onSkip(task, { refused: true, reason: "Horse refused" })}
            data-testid={`med-refuse-${task.id}`}
            className="hidden sm:inline-flex items-center justify-center px-2.5 py-1 rounded-lg text-equine-clay text-[11px] hover:bg-equine-clay/10 transition-colors"
            title="Horse refused"
          >
            Refused
          </button>
          <button
            data-testid={`med-give-${task.id}`}
            onClick={() => onComplete(task)}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-equine-navy text-white text-[12px] hover:bg-equine-navyLift active:scale-95 transition-all"
          >
            <Check className="w-3.5 h-3.5" strokeWidth={2.5} /> Given
          </button>
        </div>
      )}
    </div>
  );
};

export default function Medications() {
  const { tasks, horses, loading, complete, skip, syncStateForTask } =
    useEngineTasksToday(["medication"]);
  const [activeTemplates, setActiveTemplates] = useState([]);

  useEffect(() => {
    api
      .get("/task-templates?category=medication&active=true")
      .then((r) => setActiveTemplates(r.data.items || []))
      .catch(() => setActiveTemplates([]));
  }, []);

  const due = tasks.filter((t) => t.status !== "completed" && t.status !== "skipped").length;

  return (
    <div data-testid="medications-page">
      <PageHeader
        eyebrow="Treatment"
        title="Medications"
        subtitle="Today's doses and active prescriptions, all flowing through the unified care engine."
        action={
          <StatusPill tone={due ? "warning" : "success"}>{due ? `${due} due` : "All clear"}</StatusPill>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card data-testid="med-today-card">
          <h2 className="font-display text-2xl mb-4 text-equine-ink">Today's doses</h2>
          {loading && tasks.length === 0 ? (
            <div className="text-equine-inkSoft text-[13px] py-6 text-center">Loading…</div>
          ) : tasks.length === 0 ? (
            <div className="text-equine-inkSoft text-[13px] py-6 text-center">No doses scheduled today.</div>
          ) : (
            tasks.map((t) => (
              <DoseRow
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

        <Card data-testid="med-prescriptions-card">
          <h2 className="font-display text-2xl mb-4 text-equine-ink">Active prescriptions</h2>
          {activeTemplates.length === 0 ? (
            <div className="text-equine-inkSoft text-[13px] py-6 text-center">No active medication templates.</div>
          ) : (
            activeTemplates.map((m) => {
              const p = m.payload_defaults || {};
              const horseNames = (m.linked_horse_ids || [])
                .map((id) => horses[id]?.name)
                .filter(Boolean);
              return (
                <div key={m.id} className="py-3 hairline">
                  <div className="flex justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-equine-ink truncate">
                        {horseNames.join(", ") || "All horses"} · {p.med_name || m.title}
                      </div>
                      <div className="text-[12.5px] text-equine-inkMuted truncate">
                        {[p.dose && `${p.dose} ${p.unit || ""}`, p.route].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                    <div className="text-[12px] text-equine-inkMuted whitespace-nowrap">
                      {m.rrule ? m.rrule.replace(/^.*?FREQ=([A-Z]+).*$/, "$1").toLowerCase() : "one-off"}
                    </div>
                  </div>
                  {m.description && (
                    <div className="text-[12px] text-equine-amber mt-1 flex items-center gap-1.5">
                      <AlertTriangle className="w-3 h-3" /> {m.description}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </Card>
      </div>
    </div>
  );
}
