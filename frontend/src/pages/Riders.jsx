import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Riders() {
  const [riders, setRiders] = useState([]);
  useEffect(() => { api.get("/riders").then((r) => setRiders(r.data)); }, []);

  return (
    <div data-testid="riders-page">
      <PageHeader eyebrow="Program" title="Riders" subtitle="Track skill development, goals and lesson progress across the rider roster." />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {riders.map((r) => (
          <Card key={r.id} data-testid={`rider-${r.id}`}>
            <div className="flex items-start justify-between mb-2">
              <div className="font-display text-2xl text-equine-ivory">{r.full_name}</div>
              <StatusPill tone="neutral">{r.skill_level}</StatusPill>
            </div>
            <div className="text-[13px] text-equine-silver/80 mt-1">Goal: {r.goals}</div>
            <div className="text-[12.5px] text-equine-platinum/60 mt-2">Emergency: {r.emergency_contact}</div>
          </Card>
        ))}
      </div>
    </div>
  );
}
