import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Training() {
  const [sessions, setSessions] = useState([]);
  useEffect(() => { api.get("/training").then((r) => setSessions(r.data)); }, []);

  return (
    <div data-testid="training-page">
      <PageHeader eyebrow="Development" title="Training Log" subtitle="Daily rides, exercises, ratings, and homework — across every horse in work." />

      <Card>
        {sessions.map((t) => (
          <div key={t.id} className="py-4 hairline">
            <div className="flex items-center justify-between mb-1">
              <div className="font-display text-xl text-equine-ivory">{t.horse_name}</div>
              <StatusPill tone="neutral">{t.discipline}</StatusPill>
            </div>
            <div className="text-[12.5px] text-equine-platinum/60 mb-2">{fmtDate(t.date)} · {t.trainer_name}</div>
            <div className="text-equine-silver/80 text-[14px]">{t.exercises}</div>
            {t.notes && <div className="text-[13px] text-equine-platinum/80 mt-1.5">Notes: {t.notes}</div>}
            {t.homework && <div className="text-[12.5px] text-equine-champagne mt-1.5">Homework: {t.homework}</div>}
          </div>
        ))}
      </Card>
    </div>
  );
}
