import React, { useEffect, useState } from "react";
import { api, fmtTime } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Check, AlertTriangle, GraduationCap, BedDouble, CloudRain, UtensilsCrossed, Pill } from "lucide-react";

export default function BarnBoard() {
  const [data, setData] = useState(null);

  const load = () => api.get("/dashboard/barn-board").then((r) => setData(r.data));
  useEffect(() => { load(); }, []);

  const completeFeed = async (id) => {
    await api.post(`/feed-tasks/${id}/complete`);
    load();
  };

  if (!data) return <div className="text-equine-platinum/60">Loading…</div>;

  return (
    <div data-testid="barn-board-page">
      <PageHeader
        eyebrow={`${new Date(data.date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}`}
        title="Today's Barn Board"
        subtitle="Optimised for tablets in feed rooms and aisle stations. Tap any task to mark complete."
      />

      {/* Weather strip */}
      <Card className="mb-6 flex items-center gap-4 !py-4">
        <div className="w-12 h-12 rounded-xl bg-equine-soft border border-equine-graphite/40 flex items-center justify-center">
          <CloudRain strokeWidth={1.4} />
        </div>
        <div className="flex-1">
          <div className="label-eyebrow">Weather Advisory</div>
          <div className="text-equine-ivory">{data.weather.condition} · {data.weather.temp_f}°F — {data.weather.alert}</div>
        </div>
        <StatusPill tone="warning">Active</StatusPill>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Feed */}
        <Section icon={UtensilsCrossed} title="Feed Tasks" count={data.feed.length}>
          <ul className="space-y-3">
            {data.feed.map((t) => (
              <li key={t.id} className={`flex items-center gap-4 p-4 rounded-xl border ${t.completed ? "bg-equine-soft/60 border-equine-sage/30" : "bg-equine-soft border-equine-graphite/40"}`}>
                <div className="w-1 h-12 rounded-full" style={{ background: t.completed ? "#6E8B74" : "#C6924B" }} />
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <span className="font-display text-xl text-equine-ivory">{t.horse_name}</span>
                    <StatusPill tone="neutral">{t.meal}</StatusPill>
                  </div>
                  <div className="text-[13px] text-equine-silver/80 mt-1">{t.ration}</div>
                  {t.instructions && <div className="text-[12px] text-equine-amber mt-1">⚠ {t.instructions}</div>}
                </div>
                {t.completed ? (
                  <span className="text-equine-sage flex items-center gap-1 text-sm"><Check className="w-4 h-4" /> {t.completed_by}</span>
                ) : (
                  <button data-testid={`complete-feed-${t.id}`} onClick={() => completeFeed(t.id)} className="btn-primary text-sm">Mark fed</button>
                )}
              </li>
            ))}
          </ul>
        </Section>

        {/* Medications */}
        <Section icon={Pill} title="Medications" count={data.medications.length}>
          <ul className="space-y-3">
            {data.medications.map((m) => (
              <li key={m.id} className="flex items-center gap-4 p-4 rounded-xl bg-equine-soft border border-equine-graphite/40">
                <div className="w-1 h-12 rounded-full" style={{ background: m.status === "given" ? "#6E8B74" : "#A85C4B" }} />
                <div className="flex-1">
                  <div className="font-display text-xl text-equine-ivory">{m.horse_name}</div>
                  <div className="text-[13px] text-equine-silver/80 mt-0.5">{m.med_name} — {m.dosage} @ {fmtTime(m.scheduled_time)}</div>
                </div>
                <StatusPill tone={m.status === "given" ? "success" : "critical"}>{m.status}</StatusPill>
              </li>
            ))}
            {data.medications.length === 0 && <li className="text-equine-platinum/60 text-sm">No medications scheduled.</li>}
          </ul>
        </Section>

        {/* Lessons */}
        <Section icon={GraduationCap} title="Lessons & Rides" count={data.lessons.length}>
          <ul className="space-y-3">
            {data.lessons.map((l) => (
              <li key={l.id} className="flex items-center gap-4 p-4 rounded-xl bg-equine-soft border border-equine-graphite/40">
                <div className="font-display text-2xl text-equine-champagne w-16">{fmtTime(l.start_time)}</div>
                <div className="flex-1">
                  <div className="text-equine-ivory text-[15px]">{l.rider_name} · <span className="text-equine-silver/80">{l.horse_name}</span></div>
                  <div className="text-[12.5px] text-equine-platinum/70 mt-0.5">{l.focus} · {l.duration_min} min · {l.trainer_name}</div>
                </div>
              </li>
            ))}
          </ul>
        </Section>

        {/* Stall rest */}
        <Section icon={BedDouble} title="Stall Rest & Rehab" count={data.stall_rest.length}>
          <ul className="space-y-3">
            {data.stall_rest.map((h) => (
              <li key={h.id} className="flex items-center gap-4 p-4 rounded-xl bg-equine-soft border border-equine-graphite/40">
                <img src={h.photo_url} alt={h.name} className="w-12 h-12 rounded-xl object-cover" />
                <div className="flex-1">
                  <div className="font-display text-xl text-equine-ivory">{h.name}</div>
                  <div className="text-[12.5px] text-equine-platinum/70">{h.stall} · Wellness {h.wellness_score}</div>
                </div>
                <StatusPill tone={h.status === "rehab" ? "warning" : "critical"}>{h.status.replace('_', ' ')}</StatusPill>
              </li>
            ))}
            {data.stall_rest.length === 0 && <li className="text-equine-platinum/60 text-sm">All horses cleared for normal turnout.</li>}
          </ul>
        </Section>

        {/* Urgent */}
        {data.urgent.length > 0 && (
          <Section icon={AlertTriangle} title="Recent Incidents" count={data.urgent.length} className="lg:col-span-2">
            <ul className="space-y-3">
              {data.urgent.map((i) => (
                <li key={i.id} className="p-4 rounded-xl bg-equine-soft border border-equine-clay/30">
                  <div className="flex items-center gap-3 mb-1.5">
                    <StatusPill tone="critical">{i.severity}</StatusPill>
                    <span className="font-display text-lg text-equine-ivory">{i.title}</span>
                  </div>
                  <div className="text-[13px] text-equine-silver/80">{i.description}</div>
                  <div className="text-[11.5px] text-equine-platinum/60 mt-1.5">Reported by {i.reported_by}</div>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </div>
  );
}

const Section = ({ icon: Icon, title, count, children, className = "" }) => (
  <Card className={className}>
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <Icon strokeWidth={1.4} className="text-equine-champagne" />
        <h2 className="font-display text-2xl text-equine-ivory">{title}</h2>
      </div>
      <StatusPill tone="neutral">{count}</StatusPill>
    </div>
    {children}
  </Card>
);
