import React, { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill, Empty } from "../components/Primitives";
import QuickAddSheet from "../components/QuickAddSheet";

const ADD_FIELDS = [
  { key: "full_name", label: "Rider name", required: true, full: true, placeholder: "Amelia Vance" },
  { key: "age", label: "Age", type: "number" },
  { key: "skill_level", label: "Skill level", kind: "select", opts: ["beginner", "intermediate", "advanced"] },
  { key: "goals", label: "Goals / focus", full: true, kind: "textarea", rows: 2, placeholder: "Move up to 1.10m jumpers by summer" },
  { key: "emergency_contact", label: "Emergency contact", full: true, placeholder: "+1 555 0900" },
];

export default function Riders() {
  const [riders, setRiders] = useState([]);
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => api.get("/riders").then((r) => setRiders(r.data)), []);
  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="riders-page">
      <PageHeader
        eyebrow="Program"
        title="Riders"
        subtitle="Track skill development, goals and lesson progress across the rider roster."
        action={
          <button
            onClick={() => setAddOpen(true)}
            data-testid="riders-add-btn"
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Add rider
          </button>
        }
      />

      {riders.length === 0 ? (
        <Empty>
          <div className="font-display text-2xl text-equine-ivory mb-1">No riders yet</div>
          <div className="text-[13px] text-equine-platinum/60 mb-4">Add your first rider to schedule lessons and track development goals.</div>
          <button onClick={() => setAddOpen(true)} data-testid="riders-empty-add" className="btn-primary inline-flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add first rider
          </button>
        </Empty>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {riders.map((r) => (
            <Card key={r.id} data-testid={`rider-${r.id}`}>
              <div className="flex items-start justify-between mb-2">
                <div className="font-display text-2xl text-equine-ivory">{r.full_name}</div>
                {r.skill_level && <StatusPill tone="neutral">{r.skill_level}</StatusPill>}
              </div>
              {r.goals && <div className="text-[13px] text-equine-silver/80 mt-1">Goal: {r.goals}</div>}
              {r.emergency_contact && <div className="text-[12.5px] text-equine-platinum/60 mt-2">Emergency: {r.emergency_contact}</div>}
            </Card>
          ))}
        </div>
      )}

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add rider"
        eyebrow="Program"
        fields={ADD_FIELDS}
        endpoint="/riders"
        submitLabel="Add rider"
        testidPrefix="riders-add"
        onCreated={load}
      />
    </div>
  );
}
