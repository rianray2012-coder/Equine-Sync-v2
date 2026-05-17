import React, { useEffect, useState } from "react";
import { api, fmtDate, money } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Health() {
  const [vet, setVet] = useState([]);
  const [injuries, setInjuries] = useState([]);

  useEffect(() => {
    api.get("/vet-records").then((r) => setVet(r.data));
    api.get("/injuries").then((r) => setInjuries(r.data));
  }, []);

  return (
    <div data-testid="health-page">
      <PageHeader eyebrow="Veterinary" title="Health & Vet" subtitle="Vaccines, dentals, Coggins, exams and injury timelines for every horse." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="font-display text-2xl mb-4">Recent Vet Records</h2>
          {vet.map((v) => (
            <div key={v.id} className="py-3 hairline">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-equine-ivory">{v.horse_name} — {v.title}</div>
                  <div className="text-[12.5px] text-equine-platinum/60">{fmtDate(v.date)} · {v.vet_name}</div>
                </div>
                <div className="text-right">
                  <div className="text-equine-silver text-[13px]">{money(v.cost)}</div>
                  <StatusPill tone="neutral">{v.type}</StatusPill>
                </div>
              </div>
            </div>
          ))}
        </Card>

        <Card>
          <h2 className="font-display text-2xl mb-4">Injuries & Rehab</h2>
          {injuries.map((i) => (
            <div key={i.id} className="py-3 hairline">
              <div className="flex items-center justify-between mb-1">
                <div className="text-equine-ivory">{i.horse_name} — {i.title}</div>
                <StatusPill tone={i.status === "resolved" ? "success" : i.status === "improving" ? "warning" : "critical"}>{i.status}</StatusPill>
              </div>
              <div className="text-[12.5px] text-equine-platinum/70">{i.description}</div>
              {i.rehab_plan && <div className="text-[12.5px] text-equine-champagne mt-1.5">Plan: {i.rehab_plan}</div>}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
