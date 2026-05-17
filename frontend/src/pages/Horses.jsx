import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Search } from "lucide-react";

export default function Horses() {
  const [horses, setHorses] = useState([]);
  const [q, setQ] = useState("");

  useEffect(() => { api.get("/horses").then((r) => setHorses(r.data)); }, []);

  const filtered = horses.filter((h) =>
    [h.name, h.breed, h.discipline, h.stall].some((v) => (v || "").toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div data-testid="horses-page">
      <PageHeader
        eyebrow="Roster"
        title="Horses"
        subtitle="Every horse in the barn with at-a-glance health, discipline and stall details."
      />

      <Card hover={false} className="mb-6 !py-3 flex items-center gap-3">
        <Search strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/60" />
        <input
          placeholder="Search by name, breed, discipline…"
          value={q} onChange={(e) => setQ(e.target.value)}
          data-testid="horse-search"
          className="flex-1 bg-transparent outline-none text-equine-ivory placeholder:text-equine-platinum/40 py-1"
        />
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {filtered.map((h) => (
          <Link
            key={h.id} to={`/horses/${h.id}`}
            data-testid={`horse-card-${h.id}`}
            className="equine-card equine-card-hover overflow-hidden group block"
          >
            <div className="relative aspect-[4/3] overflow-hidden">
              <img src={h.photo_url} alt={h.name} className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-700" />
              <div className="absolute inset-0 bg-gradient-to-t from-equine-black via-equine-black/30 to-transparent" />
              <div className="absolute top-3 right-3">
                <StatusPill tone={h.status === "active" ? "success" : h.status === "stall_rest" ? "critical" : "warning"}>
                  {h.status.replace('_', ' ')}
                </StatusPill>
              </div>
              <div className="absolute bottom-3 left-4 right-4">
                <div className="font-display text-2xl text-equine-ivory leading-none">{h.name}</div>
                <div className="text-[12px] text-equine-platinum/80 mt-1.5">{h.breed} · {h.age}yrs · {h.height_hands}hh</div>
              </div>
            </div>
            <div className="p-5">
              <div className="flex justify-between items-center text-[12.5px]">
                <span className="label-eyebrow">{h.discipline}</span>
                <span className="text-equine-platinum/60">{h.stall}</span>
              </div>
              <div className="mt-3 pt-3 hairline flex justify-between items-end">
                <div>
                  <div className="label-eyebrow text-[10px]">Wellness</div>
                  <div className="font-display text-2xl text-equine-ivory">{h.wellness_score}</div>
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
    </div>
  );
}
