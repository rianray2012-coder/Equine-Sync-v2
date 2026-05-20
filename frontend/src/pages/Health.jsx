import React, { useEffect, useState } from "react";
import { api, fmtDate, fmtTime, money } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Stethoscope, Hammer, Calendar, Activity } from "lucide-react";

const UpcomingRow = ({ task, horseLookup, icon: Icon }) => {
  const horseNames = (task.linked_horse_ids || [])
    .map((id) => horseLookup[id]?.name)
    .filter(Boolean);
  const p = task.payload || {};
  return (
    <div data-testid={`upcoming-${task.id}`} className="flex items-center gap-3 py-3 hairline">
      <div className="w-9 h-9 rounded-lg bg-equine-soft flex items-center justify-center flex-shrink-0">
        <Icon strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[14px] text-equine-ink truncate">{task.title}</div>
        <div className="text-[12px] text-equine-inkMuted truncate">
          {horseNames.join(", ") || "All horses"}
          {p.vet_name && ` · ${p.vet_name}`}
          {p.farrier_name && ` · ${p.farrier_name}`}
        </div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="text-[12px] text-equine-ink">{fmtDate(task.scheduled_at)}</div>
        <div className="text-[11px] text-equine-inkSoft">{fmtTime(task.scheduled_at)}</div>
      </div>
    </div>
  );
};

export default function Health() {
  const [vet, setVet] = useState([]);
  const [farrier, setFarrier] = useState([]);
  const [injuries, setInjuries] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [horses, setHorses] = useState({});

  useEffect(() => {
    api.get("/vet-records").then((r) => setVet(r.data)).catch(() => {});
    api.get("/farrier-history").then((r) => setFarrier(r.data)).catch(() => setFarrier([]));
    api.get("/injuries").then((r) => setInjuries(r.data)).catch(() => {});
    api.get("/horses").then((r) => {
      const map = {};
      (r.data || []).forEach((h) => { map[h.id] = h; });
      setHorses(map);
    }).catch(() => {});
    // Pull upcoming vet + farrier from the unified engine (next 30 days)
    const start = new Date().toISOString();
    const end = new Date(Date.now() + 30 * 86400000).toISOString();
    Promise.all([
      api.get(`/tasks?category=vet&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
      api.get(`/tasks?category=farrier&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
    ]).then(([v, f]) => {
      const merged = [...(v.data.items || []), ...(f.data.items || [])]
        .filter((t) => t.status !== "completed" && t.status !== "skipped" && t.status !== "cancelled")
        .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
      setUpcoming(merged);
    }).catch(() => setUpcoming([]));
  }, []);

  return (
    <div data-testid="health-page">
      <PageHeader
        eyebrow="Veterinary"
        title="Health & Vet"
        subtitle="Upcoming appointments via the unified care engine; historical records and injury timelines below."
      />

      {/* Upcoming engine-sourced visits */}
      <Card className="mb-6" data-testid="upcoming-visits-card">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <Calendar strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
            <h2 className="font-display text-2xl text-equine-ink">Upcoming visits</h2>
          </div>
          <StatusPill tone="info">{upcoming.length} scheduled</StatusPill>
        </div>
        {upcoming.length === 0 ? (
          <div className="text-equine-inkSoft text-[13px] py-6 text-center italic">
            No vet or farrier visits scheduled in the next 30 days.
          </div>
        ) : (
          upcoming.map((t) => (
            <UpcomingRow
              key={t.id}
              task={t}
              horseLookup={horses}
              icon={t.category === "vet" ? Stethoscope : Hammer}
            />
          ))
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="font-display text-2xl mb-4 text-equine-ink">Recent vet records</h2>
          {vet.length === 0 && (
            <div className="text-equine-inkSoft text-[13px] py-6 text-center">No vet records yet.</div>
          )}
          {vet.slice(0, 12).map((v) => (
            <div key={v.id} className="py-3 hairline">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-equine-ink">
                    {(horses[v.horse_id]?.name) || v.horse_name || "Horse"} — {v.title}
                  </div>
                  <div className="text-[12.5px] text-equine-inkMuted">
                    {fmtDate(v.date)}{v.vet_name ? ` · ${v.vet_name}` : ""}
                    {v.source === "task_engine" && <span className="ml-2 text-equine-brass text-[10.5px] uppercase tracking-[0.18em]">via engine</span>}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-equine-inkMuted text-[13px]">{money(v.cost)}</div>
                  {v.type && <StatusPill tone="neutral">{v.type}</StatusPill>}
                </div>
              </div>
              {v.follow_up_due && (
                <div className="text-[11.5px] text-equine-saddle mt-1.5">
                  Follow-up scheduled · {fmtDate(v.follow_up_due)}
                </div>
              )}
            </div>
          ))}
        </Card>

        <Card data-testid="farrier-history-card">
          <h2 className="font-display text-2xl mb-4 text-equine-ink flex items-center gap-2">
            <Hammer className="w-4 h-4 text-equine-navy" /> Farrier history
          </h2>
          {farrier.length === 0 ? (
            <div className="text-equine-inkSoft text-[13px] py-6 text-center italic">
              Farrier visits will appear here automatically when completed.
            </div>
          ) : (
            farrier.slice(0, 12).map((f) => (
              <div key={f.id} className="py-3 hairline">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-equine-ink">
                      {(horses[f.horse_id]?.name) || "Horse"}
                      {f.farrier_name && ` · ${f.farrier_name}`}
                    </div>
                    <div className="text-[12.5px] text-equine-inkMuted">
                      {fmtDate(f.date)}
                      {f.shoes_on?.length > 0 && ` · ${f.shoes_on.join("/")}`}
                    </div>
                  </div>
                  <div className="text-right">
                    {f.cost > 0 && <div className="text-equine-inkMuted text-[13px]">{money(f.cost)}</div>}
                    {f.next_visit_due && (
                      <div className="text-[11px] text-equine-saddle">next {fmtDate(f.next_visit_due)}</div>
                    )}
                  </div>
                </div>
                {f.trim_notes && <div className="text-[12px] text-equine-inkMuted mt-1 italic">{f.trim_notes}</div>}
              </div>
            ))
          )}
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="font-display text-2xl mb-4 text-equine-ink flex items-center gap-2">
            <Activity className="w-4 h-4 text-equine-navy" /> Injuries & rehab
          </h2>
          {injuries.length === 0 && (
            <div className="text-equine-inkSoft text-[13px] py-6 text-center">No active injuries.</div>
          )}
          {injuries.map((i) => (
            <div key={i.id} className="py-3 hairline">
              <div className="flex items-center justify-between mb-1">
                <div className="text-equine-ink">{i.horse_name} — {i.title}</div>
                <StatusPill tone={i.status === "resolved" ? "success" : i.status === "improving" ? "warning" : "critical"}>
                  {i.status}
                </StatusPill>
              </div>
              <div className="text-[12.5px] text-equine-inkMuted">{i.description}</div>
              {i.rehab_plan && (
                <div className="text-[12.5px] text-equine-saddle mt-1.5">Plan: {i.rehab_plan}</div>
              )}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
