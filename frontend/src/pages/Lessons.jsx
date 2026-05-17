import React, { useEffect, useState } from "react";
import { api, fmtDate, fmtTime } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Lessons() {
  const [lessons, setLessons] = useState([]);
  const [riders, setRiders] = useState([]);
  useEffect(() => {
    api.get("/lessons").then((r) => setLessons(r.data));
    api.get("/riders").then((r) => setRiders(r.data));
  }, []);

  return (
    <div data-testid="lessons-page">
      <PageHeader eyebrow="Program" title="Lesson Program" subtitle="Schedule, rider development, and lesson horse workload monitoring." />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <h2 className="font-display text-2xl mb-4">Upcoming Lessons</h2>
          {lessons.map((l) => (
            <div key={l.id} className="py-3 hairline flex items-center gap-4">
              <div className="font-display text-xl text-equine-champagne w-28">{fmtDate(l.start_time)} · {fmtTime(l.start_time)}</div>
              <div className="flex-1">
                <div className="text-equine-ivory">{l.rider_name} on {l.horse_name}</div>
                <div className="text-[12.5px] text-equine-platinum/60">{l.focus} · {l.duration_min} min · {l.trainer_name}</div>
              </div>
              <StatusPill tone={l.completed ? "success" : "info"}>{l.completed ? "done" : "scheduled"}</StatusPill>
            </div>
          ))}
        </Card>

        <Card>
          <h2 className="font-display text-2xl mb-4">Riders</h2>
          {riders.map((r) => (
            <div key={r.id} className="py-3 hairline">
              <div className="text-equine-ivory">{r.full_name}</div>
              <div className="text-[12.5px] text-equine-platinum/60 mt-0.5">{r.skill_level} · {r.goals}</div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
