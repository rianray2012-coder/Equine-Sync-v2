import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Incidents() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/incidents").then((r) => setItems(r.data)); }, []);
  return (
    <div data-testid="incidents-page">
      <PageHeader eyebrow="Safety" title="Incident Reports" subtitle="Documented events with timelines, severities and owner sign-offs." />
      <Card>
        {items.length === 0 && <div className="text-equine-platinum/60 text-sm">No incidents reported.</div>}
        {items.map((i) => (
          <div key={i.id} className="py-4 hairline">
            <div className="flex items-center justify-between mb-1">
              <div className="font-display text-xl text-equine-ivory">{i.title}</div>
              <StatusPill tone={i.severity === "severe" ? "critical" : "warning"}>{i.severity}</StatusPill>
            </div>
            <div className="text-[12.5px] text-equine-platinum/60">{fmtDate(i.occurred_at)} · {i.horse_name} · Reported by {i.reported_by}</div>
            <div className="text-equine-silver/80 text-[14px] mt-2">{i.description}</div>
            {i.follow_up && <div className="text-[13px] text-equine-champagne mt-2">Follow-up: {i.follow_up}</div>}
          </div>
        ))}
      </Card>
    </div>
  );
}
