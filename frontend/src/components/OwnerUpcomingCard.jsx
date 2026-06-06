import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card } from "./Primitives";
import { CalendarClock, Stethoscope, Hammer, Activity } from "lucide-react";

/**
 * Phase 7D-2 — owner-facing, READ-ONLY "Looking ahead" card.
 *
 * Consumes the owner-scoped GET /api/owner/upcoming (vet/farrier/rehab in the
 * next 14 days, owned horses only). Display-only; the friendly countdown is
 * computed client-side.
 */
const CAT_META = {
  vet: { label: "Vet", icon: Stethoscope },
  farrier: { label: "Farrier", icon: Hammer },
  rehab: { label: "Rehab", icon: Activity },
};

const dayDiff = (iso) => {
  const d = new Date(iso);
  const today = new Date();
  d.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  return Math.round((d - today) / 86400000);
};

const countdown = (iso) => {
  const n = dayDiff(iso);
  if (n <= 0) return "Today";
  if (n === 1) return "Tomorrow";
  return `In ${n} days`;
};

export default function OwnerUpcomingCard() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .get("/owner/upcoming")
      .then((r) => setItems(Array.isArray(r.data) ? r.data : []))
      .catch(() => { setError(true); setItems([]); });
  }, []);

  return (
    <Card className="mb-8" data-testid="owner-upcoming-card">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
          <CalendarClock strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
        </div>
        <div>
          <h2 className="font-display text-2xl text-equine-ink">Looking ahead</h2>
          <div className="text-[12.5px] text-equine-inkMuted">Upcoming vet, farrier and rehab visits over the next two weeks.</div>
        </div>
      </div>

      {items === null && (
        <div className="py-8 text-center text-equine-inkSoft text-[13px]">Checking the calendar…</div>
      )}

      {error && items !== null && (
        <div className="py-8 text-center text-equine-inkSoft text-[13px]" data-testid="owner-upcoming-error">
          We couldn&apos;t load your schedule right now. Please try again shortly.
        </div>
      )}

      {!error && items !== null && items.length === 0 && (
        <div className="py-8 text-center text-equine-inkSoft text-[13px]" data-testid="owner-upcoming-empty">
          Nothing scheduled in the coming weeks.
        </div>
      )}

      {!error && items !== null && items.length > 0 && (
        <div className="space-y-2">
          {items.map((u) => {
            const meta = CAT_META[u.category] || { label: u.category, icon: CalendarClock };
            const Icon = meta.icon;
            return (
              <div
                key={u.id}
                data-testid={`owner-upcoming-item-${u.id}`}
                className="flex items-center gap-3 py-2.5 hairline flex-wrap"
              >
                <div className="w-8 h-8 rounded-lg bg-equine-soft border border-equine-hairline flex items-center justify-center shrink-0">
                  <Icon strokeWidth={1.5} className="w-3.5 h-3.5 text-equine-navy" />
                </div>
                <div className="flex-1 min-w-[160px]">
                  <div className="text-[13.5px] text-equine-ink">{u.title || meta.label}</div>
                  <div className="text-[12px] text-equine-inkMuted">
                    {u.horse_name || "Your horse"} · {u.scheduled_at ? fmtDate(u.scheduled_at) : "—"}
                  </div>
                </div>
                <span className="text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full bg-equine-soft border border-equine-hairline text-equine-inkMuted">
                  {meta.label}
                </span>
                <span className="text-[12px] font-medium text-equine-navy whitespace-nowrap" data-testid={`owner-upcoming-countdown-${u.id}`}>
                  {u.scheduled_at ? countdown(u.scheduled_at) : ""}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
