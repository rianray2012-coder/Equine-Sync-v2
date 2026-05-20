import React from "react";
import { Card } from "../Primitives";
import { GraduationCap } from "lucide-react";
import { money } from "../../lib/api";

/** Operational counters — engine-derived. Calm, no fake percentages. */
export const OperationsCard = ({ summary }) => (
  <Card data-testid="operations-card">
    <div className="flex items-start justify-between mb-4">
      <div>
        <div className="label-eyebrow">Operations</div>
        <h3 className="font-display text-2xl text-equine-ivory mt-1">Today&apos;s flow</h3>
      </div>
      <GraduationCap strokeWidth={1.4} className="text-equine-brassLight" />
    </div>
    <div className="text-equine-silver/85 text-sm">
      <Row label="Lessons today" value={summary?.lessons_today ?? 0} />
      <Row label="Owner requests" value={summary?.pending_service_requests ?? 0} accent="amber" />
      <Row label="Feed tasks remaining" value={summary?.feed_pending ?? 0} />
      <Row label="Stall rest horses" value={summary?.stall_rest ?? 0} accent="clay" last />
    </div>
  </Card>
);

const ACCENTS = { ivory: "text-equine-ivory", amber: "text-equine-amber", clay: "text-equine-clay" };

const Row = ({ label, value, accent = "ivory", last = false }) => (
  <div className={`flex justify-between py-2.5 ${last ? "" : "hairline"}`}>
    <span>{label}</span>
    <span className={ACCENTS[accent]}>{value}</span>
  </div>
);

/**
 * UpcomingCareCard — replaces the previous fake-percentage WellnessPulseCard.
 * Surfaces the next handful of scheduled vet / farrier / rehab tasks from the
 * unified engine. Real data, no analytics theatre.
 */
export const UpcomingCareCard = ({ upcoming = [], loading = false }) => {
  const items = upcoming.slice(0, 4);
  return (
    <Card data-testid="upcoming-care-card">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="label-eyebrow">Care · Looking ahead</div>
          <h3 className="font-display text-2xl text-equine-ivory mt-1">Upcoming visits</h3>
        </div>
      </div>
      {loading ? (
        <div className="text-[12.5px] text-equine-platinum/60 py-3">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-[12.5px] text-equine-platinum/65 py-3 leading-relaxed">
          No scheduled vet, farrier or rehab visits in the next week. A quiet stretch.
        </div>
      ) : (
        <ul className="space-y-2.5">
          {items.map((t) => (
            <li key={t.id} className="flex items-start gap-3 text-[13px]">
              <span className="uppercase tracking-[0.18em] text-[10px] text-equine-brass/75 mt-0.5 w-14 flex-shrink-0">
                {t.category}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-equine-ivory truncate">{t.title}</div>
                <div className="text-equine-platinum/55 text-[11.5px] truncate">
                  {fmtDay(t.scheduled_at)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
};

const fmtDay = (iso) => {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  } catch { return ""; }
};

// money import retained for future revenue-tile sub-component
export { money };
