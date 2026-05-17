import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Check, UtensilsCrossed } from "lucide-react";

export default function Feed() {
  const [tasks, setTasks] = useState([]);
  const today = new Date().toISOString().slice(0, 10);

  const load = () => api.get(`/feed-tasks?date_str=${today}`).then((r) => setTasks(r.data));
  useEffect(() => { load(); }, []);

  const groups = ["morning", "midday", "evening"];
  const done = tasks.filter((t) => t.completed).length;

  return (
    <div data-testid="feed-page">
      <PageHeader
        eyebrow="Feed Room"
        title="Today's Feeding"
        subtitle="Triple-check medication-laced rations. Sign off each meal as it's delivered."
        action={<StatusPill tone="success">{done} of {tasks.length} completed</StatusPill>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {groups.map((g) => {
          const grp = tasks.filter((t) => t.meal === g);
          return (
            <Card key={g}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display text-2xl capitalize">{g}</h2>
                <UtensilsCrossed strokeWidth={1.4} className="text-equine-champagne" />
              </div>
              {grp.map((t) => (
                <div key={t.id} className="py-3 hairline">
                  <div className="flex items-center justify-between">
                    <div className="font-display text-lg text-equine-ivory">{t.horse_name}</div>
                    {t.completed ? <Check className="text-equine-sage w-5 h-5" /> : (
                      <button data-testid={`feed-complete-${t.id}`} onClick={async () => { await api.post(`/feed-tasks/${t.id}/complete`); load(); }} className="btn-primary !py-1 !px-3 text-[12px]">Mark</button>
                    )}
                  </div>
                  <div className="text-[12.5px] text-equine-platinum/70 mt-1">{t.ration}</div>
                  {t.instructions && <div className="text-[11.5px] text-equine-amber mt-1">⚠ {t.instructions}</div>}
                </div>
              ))}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
