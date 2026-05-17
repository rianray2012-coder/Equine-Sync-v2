import React, { useEffect, useState } from "react";
import { api, fmtTime } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Medications() {
  const [logs, setLogs] = useState([]);
  const [meds, setMeds] = useState([]);

  useEffect(() => {
    api.get("/medication-logs").then((r) => setLogs(r.data));
    api.get("/medications").then((r) => setMeds(r.data));
  }, []);

  return (
    <div data-testid="medications-page">
      <PageHeader eyebrow="Treatment" title="Medications" subtitle="Active prescriptions, today's doses and missed treatment alerts." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="font-display text-2xl mb-4">Today's doses</h2>
          {logs.length === 0 && <div className="text-equine-platinum/60 text-sm">No doses scheduled.</div>}
          {logs.map((l) => (
            <div key={l.id} className="flex items-center gap-4 py-3 hairline">
              <div className="font-display text-xl text-equine-champagne w-20">{fmtTime(l.scheduled_time)}</div>
              <div className="flex-1">
                <div className="text-equine-ivory">{l.horse_name} — {l.med_name}</div>
                <div className="text-[12.5px] text-equine-platinum/60">{l.dosage}</div>
              </div>
              <StatusPill tone={l.status === "given" ? "success" : "critical"}>{l.status}</StatusPill>
            </div>
          ))}
        </Card>

        <Card>
          <h2 className="font-display text-2xl mb-4">Active prescriptions</h2>
          {meds.map((m) => (
            <div key={m.id} className="py-3 hairline">
              <div className="flex justify-between">
                <div className="text-equine-ivory">{m.horse_name} · {m.name}</div>
                <div className="text-[12.5px] text-equine-platinum/60">{m.frequency}</div>
              </div>
              <div className="text-[12.5px] text-equine-platinum/70 mt-1">{m.dosage} · {m.route} · Rx: {m.prescribing_vet}</div>
              {m.notes && <div className="text-[12px] text-equine-amber mt-1">⚠ {m.notes}</div>}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
