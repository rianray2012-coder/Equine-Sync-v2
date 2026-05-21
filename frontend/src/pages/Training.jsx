import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Dumbbell } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill, Empty } from "../components/Primitives";
import QuickAddSheet from "../components/QuickAddSheet";
import SoftWarning from "../components/SoftWarning";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function Training() {
  const [sessions, setSessions] = useState([]);
  const [horses, setHorses] = useState([]);
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => api.get("/training").then((r) => setSessions(r.data)), []);
  useEffect(() => {
    load();
    api.get("/horses").then((r) => setHorses(r.data));
  }, [load]);

  const fields = useMemo(() => [
    {
      key: "horse_id", label: "Horse", kind: "select", required: true, full: true,
      opts: horses.length === 0
        ? [{ v: "__none__", l: "— No horses yet —" }]
        : horses.map((h) => ({ v: h.id, l: h.name })),
    },
    { key: "date", label: "Date", type: "date", required: true },
    { key: "discipline", label: "Discipline", placeholder: "Show Jumping" },
    { key: "exercises", label: "Exercises", full: true, kind: "textarea", rows: 3,
      placeholder: "Trot poles, canter transitions, gymnastic line 2-1-2." },
    { key: "notes", label: "Notes", full: true, kind: "textarea", rows: 2 },
    { key: "rating", label: "Rating (1–10)", type: "number", placeholder: "8" },
    { key: "homework", label: "Homework" },
  ], [horses]);

  const horsesEmpty = horses.length === 0;

  // Soft per-horse-per-day awareness — informational only.
  const renderWarnings = useCallback((form) => {
    if (!form?.horse_id || form.horse_id === "__none__" || !form?.date) return null;
    const clash = sessions.find(
      (s) => s.horse_id === form.horse_id && s.date === form.date,
    );
    if (!clash) return null;
    return (
      <SoftWarning testid="training-add-conflict">
        {`${clash.horse_name || "This horse"} already has training logged for ${fmtDate(form.date)}.`}
      </SoftWarning>
    );
  }, [sessions]);

  return (
    <div data-testid="training-page">
      <PageHeader
        eyebrow="Development"
        title="Training Log"
        subtitle="Daily rides, exercises, ratings, and homework — across every horse in work."
        action={
          <button
            onClick={() => setAddOpen(true)}
            disabled={horsesEmpty}
            data-testid="training-add-btn"
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            title={horsesEmpty ? "Add a horse first" : ""}
          >
            <Plus className="w-4 h-4" /> Log session
          </button>
        }
      />

      {sessions.length === 0 ? (
        <Empty>
          <Dumbbell strokeWidth={1.4} className="w-7 h-7 mx-auto mb-3 text-equine-champagne" />
          <div className="font-display text-2xl text-equine-ivory mb-1">No training sessions logged</div>
          <div className="text-[13px] text-equine-platinum/60 mb-4">Log the work — exercises, ratings, homework — to build each horse's development arc.</div>
          {!horsesEmpty && (
            <button onClick={() => setAddOpen(true)} data-testid="training-empty-add" className="btn-primary inline-flex items-center gap-2">
              <Plus className="w-4 h-4" /> Log first session
            </button>
          )}
        </Empty>
      ) : (
        <Card>
          {sessions.map((t) => (
            <div key={t.id} data-testid={`training-${t.id}`} className="py-4 hairline">
              <div className="flex items-center justify-between mb-1 gap-3">
                <div className="font-display text-xl text-equine-ivory">{t.horse_name || "—"}</div>
                {t.discipline && <StatusPill tone="neutral">{t.discipline}</StatusPill>}
              </div>
              <div className="text-[12.5px] text-equine-platinum/60 mb-2">
                {fmtDate(t.date)}{t.trainer_name ? ` · ${t.trainer_name}` : ""}
                {t.rating ? ` · ${t.rating}/10` : ""}
              </div>
              {t.exercises && <div className="text-equine-silver/80 text-[14px]">{t.exercises}</div>}
              {t.notes && <div className="text-[13px] text-equine-platinum/80 mt-1.5">Notes: {t.notes}</div>}
              {t.homework && <div className="text-[12.5px] text-equine-champagne mt-1.5">Homework: {t.homework}</div>}
            </div>
          ))}
        </Card>
      )}

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Log training session"
        eyebrow="Development"
        fields={fields}
        endpoint="/training"
        initialValues={{ date: todayISO() }}
        transform={(form) => ({ ...form, date: form.date || todayISO() })}
        renderWarnings={renderWarnings}
        submitLabel="Save session"
        testidPrefix="training-add"
        onCreated={load}
      />

      {/* Mobile FAB — log the ride before you forget. Hidden if no horses. */}
      {!horsesEmpty && (
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="fab lg:hidden"
          data-testid="training-fab"
          aria-label="Log training session"
        >
          <Plus strokeWidth={1.8} className="w-7 h-7" />
        </button>
      )}
    </div>
  );
}
