import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card } from "./Primitives";
import { Megaphone } from "lucide-react";
import { Logo } from "./Logo";

/**
 * Phase 7C-1 — owner-facing "Updates from your barn" feed.
 *
 * Read-only. The backend (`GET /api/owner-updates`) already scopes a
 * horse_owner to ONLY their own horses' `published` + `owner_facing`
 * updates, so this component simply renders what it receives — no
 * composer, no review actions (those land in 7C-2 / 7C-3).
 */
const KIND_META = {
  routine: { label: "Care" },
  training: { label: "Training" },
  wellness: { label: "Wellness" },
  incident: { label: "Notice" },
  billing: { label: "Billing" },
  recap: { label: "Recap" },
};

const groupByDay = (items) => {
  const groups = new Map();
  for (const u of items) {
    const d = new Date(u.published_at || u.created_at);
    const key = d.toDateString();
    if (!groups.has(key)) groups.set(key, { date: d, items: [] });
    groups.get(key).items.push(u);
  }
  return Array.from(groups.values()).sort((a, b) => b.date - a.date);
};

export default function OwnerUpdatesFeed({ horses = [] }) {
  const [items, setItems] = useState(null);

  useEffect(() => {
    api
      .get("/owner-updates")
      .then((r) => setItems(Array.isArray(r.data) ? r.data : []))
      .catch(() => setItems([]));
  }, []);

  const horseName = (id) => horses.find((h) => h.id === id)?.name || "Your horse";

  return (
    <Card className="mb-8" data-testid="owner-updates-feed">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
          <Megaphone strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
        </div>
        <div>
          <h2 className="font-display text-2xl text-equine-ink">Updates from your barn</h2>
          <div className="text-[12.5px] text-equine-inkMuted">
            Notes your barn team has chosen to share with you.
          </div>
        </div>
      </div>

      {items === null && (
        <div className="py-10 text-center text-equine-inkSoft text-[13px]" data-testid="owner-updates-loading">
          Gathering recent updates…
        </div>
      )}

      {items !== null && items.length === 0 && (
        <div className="py-10 text-center" data-testid="owner-updates-empty">
          <div className="opacity-60 flex justify-center mb-2"><Logo variant="icon" size={80} /></div>
          <div className="text-[13.5px] text-equine-ink">No new updates from the barn just yet.</div>
          <div className="text-[12px] text-equine-inkMuted mt-1">
            When your team shares a note about your horse, it will appear here.
          </div>
        </div>
      )}

      {items !== null && items.length > 0 && (
        <div className="space-y-7">
          {groupByDay(items).map(({ date, items: dayItems }) => (
            <section key={date.toISOString()}>
              <div className="flex items-center gap-3 mb-3">
                <div className="text-[10.5px] uppercase tracking-[0.22em] text-equine-inkSoft font-semibold">
                  {fmtDate(date.toISOString())}
                </div>
                <div className="flex-1 h-px bg-equine-hairline" />
              </div>
              <div className="space-y-3">
                {dayItems.map((u) => (
                  <div
                    key={u.id}
                    data-testid={`owner-update-${u.id}`}
                    className="bg-equine-card rounded-xl border border-equine-hairline px-4 py-3"
                  >
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full bg-equine-soft border border-equine-hairline text-equine-inkMuted">
                        {(KIND_META[u.kind] || { label: "Update" }).label}
                      </span>
                      <span className="text-[12px] text-equine-inkMuted">{horseName(u.horse_id)}</span>
                    </div>
                    <p className="text-[13.5px] text-equine-ink leading-relaxed whitespace-pre-line">
                      {u.body}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </Card>
  );
}
