import React, { useEffect, useState } from "react";
import { api, fmtDate, fmtTime } from "../lib/api";
import { Card } from "./Primitives";
import {
  UtensilsCrossed, Pill, Hammer, Stethoscope, Activity, Sparkles, Calendar,
  Trees, BedDouble, Circle,
} from "lucide-react";

const CATEGORY_META = {
  feed:        { label: "Feeding",    icon: UtensilsCrossed },
  medication:  { label: "Medication", icon: Pill            },
  farrier:     { label: "Farrier",    icon: Hammer          },
  vet:         { label: "Veterinary", icon: Stethoscope     },
  rehab:       { label: "Rehab",      icon: Activity        },
  turnout_out: { label: "Turnout",    icon: Trees           },
  turnout_in:  { label: "Bring-in",   icon: Trees           },
  stall_clean: { label: "Stall",      icon: BedDouble       },
  custom:      { label: "Task",       icon: Circle          },
};

const OUTCOME_PHRASING = {
  done:    "completed",
  partial: "partially completed",
  skipped: "skipped",
  refused: "refused",
  issue:   "noted as an issue",
};

const fmtFollowUp = (raw) => {
  if (!raw) return null;
  try {
    const d = new Date(raw);
    if (isNaN(d)) return null;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch { return null; }
};

const phrase = (ev) => {
  const cat = CATEGORY_META[ev.category];
  if (!cat) return ev.payload_snapshot?.title || "Care update";
  const snap = ev.payload_snapshot || {};
  const title = snap.title || cat.label;
  const outcome = snap.outcome;
  const verb = outcome ? OUTCOME_PHRASING[outcome] || "completed" : "completed";
  return `${title} ${verb}`;
};

/** Returns small grey footnote lines underneath the headline. */
const detailsFor = (ev) => {
  const snap = ev.payload_snapshot || {};
  const lines = [];
  if (snap.vet_name) lines.push(`with ${snap.vet_name}`);
  if (snap.farrier_name) lines.push(`with ${snap.farrier_name}`);
  if (snap.cost && snap.cost > 0) lines.push(`$${Number(snap.cost).toLocaleString()}`);
  const followUp = fmtFollowUp(snap.follow_up_due || snap.next_visit_due);
  if (followUp) lines.push(`next due ${followUp}`);
  if (snap.notes) lines.push(snap.notes);
  return lines;
};

const groupByDay = (items) => {
  const groups = new Map();
  for (const ev of items) {
    const d = new Date(ev.occurred_at);
    const key = d.toDateString();
    if (!groups.has(key)) groups.set(key, { date: d, items: [] });
    groups.get(key).items.push(ev);
  }
  return Array.from(groups.values()).sort((a, b) => b.date - a.date);
};

/**
 * Curated owner-visible timeline. When current user is `horse_owner`,
 * the backend already filters to {medication, farrier, vet, rehab, feed}
 * completed events only. Pass `owner_view=true` for explicit signal.
 */
export default function CuratedTimeline({ horseId, limit = 40, ownerView = true }) {
  const [items, setItems] = useState(null);

  useEffect(() => {
    if (!horseId) { setItems([]); return; }
    api
      .get(`/horses/${horseId}/timeline?owner_view=${ownerView}&limit=${limit}`)
      .then((r) => setItems(r.data.items || []))
      .catch(() => setItems([]));
  }, [horseId, limit, ownerView]);

  if (items === null) {
    return (
      <div className="py-10 text-center text-equine-inkSoft text-[13px]">
        Gathering recent care…
      </div>
    );
  }
  if (!items.length) {
    return (
      <div className="py-10 text-center">
        <Sparkles className="w-6 h-6 text-equine-brassLight mx-auto mb-2" />
        <div className="text-[13.5px] text-equine-ink">A quiet stretch.</div>
        <div className="text-[12px] text-equine-inkMuted mt-1">
          Curated updates will appear here as your horse moves through the week.
        </div>
      </div>
    );
  }

  const days = groupByDay(items);

  return (
    <div data-testid="curated-timeline" className="space-y-7">
      {days.map(({ date, items: dayItems }) => (
        <section key={date.toISOString()}>
          <div className="flex items-center gap-3 mb-3">
            <Calendar className="w-3.5 h-3.5 text-equine-inkSoft" />
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-equine-inkSoft font-semibold">
              {fmtDate(date.toISOString())}
            </div>
            <div className="flex-1 h-px bg-equine-hairline" />
          </div>
          <ol className="relative ml-2 pl-5 border-l border-equine-hairline space-y-3.5">
            {dayItems.map((ev) => {
              const meta = CATEGORY_META[ev.category] || { label: "Update", icon: Sparkles };
              const Icon = meta.icon;
              return (
                <li key={ev.id} className="relative">
                  <span className="absolute -left-[27px] top-1.5 w-3.5 h-3.5 rounded-full bg-equine-card border-2 border-equine-brassLight" />
                  <div className="bg-equine-card rounded-xl border border-equine-hairline px-4 py-3">
                    <div className="flex items-start gap-3">
                      <div className="w-9 h-9 rounded-lg bg-equine-soft flex items-center justify-center flex-shrink-0">
                        <Icon strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[13.5px] text-equine-ink font-medium">{phrase(ev)}</div>
                        <div className="text-[11.5px] text-equine-inkMuted mt-0.5 flex items-center gap-2 flex-wrap">
                          <span>{fmtTime(ev.occurred_at)}</span>
                          {detailsFor(ev).map((line, i) => (
                            <React.Fragment key={i}>
                              <span className="text-equine-inkSoft">·</span>
                              <span className="truncate max-w-[260px]">{line}</span>
                            </React.Fragment>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
