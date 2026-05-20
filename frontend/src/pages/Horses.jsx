import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill, Empty } from "../components/Primitives";
import { Search, Plus } from "lucide-react";
import QuickAddSheet from "../components/QuickAddSheet";

const ADD_FIELDS = [
  { key: "name", label: "Show name", required: true, placeholder: "Valentino" },
  { key: "barn_name", label: "Barn name", placeholder: "Val" },
  { key: "breed", label: "Breed", placeholder: "Hanoverian" },
  { key: "age", label: "Age", type: "number" },
  { key: "color", label: "Color", placeholder: "Bay" },
  { key: "height_hands", label: "Height (hh)", type: "number", placeholder: "16.3" },
  { key: "discipline", label: "Discipline", placeholder: "Show Jumping" },
  { key: "stall", label: "Stall / Location", placeholder: "Stall 1" },
  { key: "turnout_group", label: "Turnout group", placeholder: "Geldings A" },
  { key: "status", label: "Status", kind: "select", opts: ["active", "stall_rest", "rehab", "retired"] },
  { key: "feed_plan", label: "Feed notes", full: true, kind: "textarea", rows: 2 },
];

export default function Horses() {
  const [horses, setHorses] = useState([]);
  const [q, setQ] = useState("");
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => api.get("/horses").then((r) => setHorses(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const filtered = horses.filter((h) =>
    [h.name, h.breed, h.discipline, h.stall].some((v) => (v || "").toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div data-testid="horses-page">
      <PageHeader
        eyebrow="Roster"
        title="Horses"
        subtitle="Every horse in the barn with at-a-glance health, discipline and stall details."
        action={
          <button
            onClick={() => setAddOpen(true)}
            data-testid="horses-add-btn"
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Add horse
          </button>
        }
      />

      {horses.length > 0 && (
        <Card hover={false} className="mb-6 !py-3 flex items-center gap-3">
          <Search strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/60" />
          <input
            placeholder="Search by name, breed, discipline…"
            value={q} onChange={(e) => setQ(e.target.value)}
            data-testid="horse-search"
            className="flex-1 bg-transparent outline-none text-equine-ivory placeholder:text-equine-platinum/40 py-1"
          />
        </Card>
      )}

      {horses.length === 0 ? (
        <Empty>
          <div className="font-display text-2xl text-equine-ivory mb-1">No horses yet</div>
          <div className="text-[13px] text-equine-platinum/60 mb-4">Add your first horse — or use Setup Concierge to bulk-import via CSV.</div>
          <button onClick={() => setAddOpen(true)} data-testid="horses-empty-add" className="btn-primary inline-flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add first horse
          </button>
        </Empty>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {filtered.map((h) => (
            <Link
              key={h.id} to={`/horses/${h.id}`}
              data-testid={`horse-card-${h.id}`}
              className="equine-card equine-card-hover overflow-hidden group block"
            >
              <div className="relative aspect-[4/3] overflow-hidden bg-equine-soft">
                {h.photo_url ? (
                  <img src={h.photo_url} alt={h.name} className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-700" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-equine-platinum/30 font-display text-5xl">
                    {h.name?.[0]}
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-equine-black via-equine-black/30 to-transparent" />
                <div className="absolute top-3 right-3">
                  <StatusPill tone={h.status === "active" ? "success" : h.status === "stall_rest" ? "critical" : "warning"}>
                    {(h.status || "active").replace('_', ' ')}
                  </StatusPill>
                </div>
                <div className="absolute bottom-3 left-4 right-4">
                  <div className="font-display text-2xl text-equine-ivory leading-none">{h.name}</div>
                  <div className="text-[12px] text-equine-platinum/80 mt-1.5">
                    {[h.breed, h.age ? `${h.age}yrs` : null, h.height_hands ? `${h.height_hands}hh` : null]
                      .filter(Boolean).join(" · ")}
                  </div>
                </div>
              </div>
              <div className="p-5">
                <div className="flex justify-between items-center text-[12.5px]">
                  <span className="label-eyebrow">{h.discipline || "—"}</span>
                  <span className="text-equine-platinum/60">{h.stall || "—"}</span>
                </div>
                <div className="mt-3 pt-3 hairline flex justify-between items-end">
                  <div>
                    <div className="label-eyebrow text-[10px]">Wellness</div>
                    <div className="font-display text-2xl text-equine-ivory">{h.wellness_score ?? 85}</div>
                  </div>
                  <div className="text-right">
                    <div className="label-eyebrow text-[10px]">Turnout</div>
                    <div className="text-[13px] text-equine-silver">{h.turnout_group || "—"}</div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add horse"
        eyebrow="Roster"
        fields={ADD_FIELDS}
        endpoint="/horses"
        submitLabel="Add horse"
        testidPrefix="horses-add"
        onCreated={load}
      />
    </div>
  );
}
