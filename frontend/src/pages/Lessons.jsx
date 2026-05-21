import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, GraduationCap } from "lucide-react";
import { api, fmtDate, fmtTime } from "../lib/api";
import { Card, PageHeader, StatusPill, Empty } from "../components/Primitives";
import QuickAddSheet from "../components/QuickAddSheet";
import SoftWarning from "../components/SoftWarning";

const CONFLICT_WINDOW_MIN = 60;

function defaultStart() {
  // Next round half-hour
  const d = new Date();
  d.setMinutes(d.getMinutes() + 60);
  d.setSeconds(0, 0);
  d.setMinutes(d.getMinutes() < 30 ? 0 : 30);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function Lessons() {
  const [lessons, setLessons] = useState([]);
  const [riders, setRiders] = useState([]);
  const [horses, setHorses] = useState([]);
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => api.get("/lessons").then((r) => setLessons(r.data)), []);
  useEffect(() => {
    load();
    api.get("/riders").then((r) => setRiders(r.data));
    api.get("/horses").then((r) => setHorses(r.data));
  }, [load]);

  const fields = useMemo(() => [
    {
      key: "rider_id", label: "Rider", kind: "select", required: true, full: true,
      opts: riders.length === 0
        ? [{ v: "__none__", l: "— No riders yet —" }]
        : riders.map((r) => ({ v: r.id, l: r.full_name })),
    },
    {
      key: "horse_id", label: "Horse", kind: "select", full: true,
      opts: [{ v: "__none__", l: "— TBD —" }, ...horses.map((h) => ({ v: h.id, l: h.name }))],
    },
    { key: "start_time", label: "Start time", type: "datetime-local", required: true },
    { key: "duration_min", label: "Duration (min)", type: "number", placeholder: "60" },
    { key: "focus", label: "Focus", full: true, placeholder: "Gymnastic grid · lateral work · position" },
  ], [riders, horses]);

  const transform = (form) => ({
    ...form,
    start_time: form.start_time ? new Date(form.start_time).toISOString() : new Date().toISOString(),
    duration_min: form.duration_min ? Number(form.duration_min) : 60,
    horse_id: form.horse_id && form.horse_id !== "__none__" ? form.horse_id : null,
  });

  // Soft scheduling-conflict awareness — never blocks, never alarms.
  // Looks for any existing lesson within ±60 min of the proposed start
  // time involving the same rider OR the same horse. Calm copy per
  // founder direction ("supportive, not corrective").
  const renderWarnings = useCallback((form) => {
    if (!form?.start_time) return null;
    const start = new Date(form.start_time).getTime();
    if (Number.isNaN(start)) return null;
    const windowMs = CONFLICT_WINDOW_MIN * 60 * 1000;
    const notes = [];

    if (form.rider_id && form.rider_id !== "__none__") {
      const clash = lessons.find((l) => {
        if (l.rider_id !== form.rider_id || !l.start_time) return false;
        const t = new Date(l.start_time).getTime();
        return Math.abs(t - start) <= windowMs;
      });
      if (clash) {
        notes.push({
          key: "rider",
          msg: `${clash.rider_name || "This rider"} already has a lesson scheduled nearby in time (${fmtDate(clash.start_time)} ${fmtTime(clash.start_time)}).`,
        });
      }
    }

    if (form.horse_id && form.horse_id !== "__none__") {
      const clash = lessons.find((l) => {
        if (l.horse_id !== form.horse_id || !l.start_time) return false;
        const t = new Date(l.start_time).getTime();
        return Math.abs(t - start) <= windowMs;
      });
      if (clash) {
        notes.push({
          key: "horse",
          msg: `${clash.horse_name || "This horse"} already has a lesson scheduled nearby in time (${fmtDate(clash.start_time)} ${fmtTime(clash.start_time)}).`,
        });
      }
    }

    if (!notes.length) return null;
    return (
      <div className="space-y-2">
        {notes.map((n) => (
          <SoftWarning key={n.key} testid={`lessons-add-conflict-${n.key}`}>
            {n.msg}
          </SoftWarning>
        ))}
      </div>
    );
  }, [lessons]);

  const ridersEmpty = riders.length === 0;

  return (
    <div data-testid="lessons-page">
      <PageHeader
        eyebrow="Program"
        title="Lesson Program"
        subtitle="Schedule, rider development, and lesson horse workload monitoring."
        action={
          <button
            onClick={() => setAddOpen(true)}
            disabled={ridersEmpty}
            data-testid="lessons-add-btn"
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            title={ridersEmpty ? "Add a rider first" : ""}
          >
            <Plus className="w-4 h-4" /> Schedule lesson
          </button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <h2 className="font-display text-2xl mb-4">Upcoming Lessons</h2>
          {lessons.length === 0 ? (
            <Empty>
              <GraduationCap strokeWidth={1.4} className="w-7 h-7 mx-auto mb-3 text-equine-champagne" />
              <div className="font-display text-2xl text-equine-ivory mb-1">No lessons scheduled</div>
              <div className="text-[13px] text-equine-platinum/60 mb-4">
                {ridersEmpty
                  ? "Add a rider first, then come back to schedule their first lesson."
                  : "Schedule a lesson to get the trainer's day moving."}
              </div>
              {!ridersEmpty && (
                <button onClick={() => setAddOpen(true)} data-testid="lessons-empty-add" className="btn-primary inline-flex items-center gap-2">
                  <Plus className="w-4 h-4" /> Schedule first lesson
                </button>
              )}
            </Empty>
          ) : (
            lessons.map((l) => (
              <div key={l.id} data-testid={`lesson-${l.id}`} className="py-3 hairline flex items-center gap-4">
                <div className="font-display text-xl text-equine-champagne w-28 shrink-0">{fmtDate(l.start_time)} · {fmtTime(l.start_time)}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-equine-ivory truncate">
                    {l.rider_name || "—"}{l.horse_name ? ` on ${l.horse_name}` : ""}
                  </div>
                  <div className="text-[12.5px] text-equine-platinum/60 truncate">
                    {[l.focus, l.duration_min ? `${l.duration_min} min` : null, l.trainer_name]
                      .filter(Boolean).join(" · ")}
                  </div>
                </div>
                <StatusPill tone={l.completed ? "success" : "info"}>{l.completed ? "done" : "scheduled"}</StatusPill>
              </div>
            ))
          )}
        </Card>

        <Card>
          <h2 className="font-display text-2xl mb-4">Riders</h2>
          {riders.length === 0 ? (
            <div className="text-[13px] text-equine-platinum/60 py-2">No riders yet.</div>
          ) : riders.map((r) => (
            <div key={r.id} className="py-3 hairline">
              <div className="text-equine-ivory">{r.full_name}</div>
              <div className="text-[12.5px] text-equine-platinum/60 mt-0.5">{r.skill_level}{r.goals ? ` · ${r.goals}` : ""}</div>
            </div>
          ))}
        </Card>
      </div>

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Schedule lesson"
        eyebrow="Program"
        fields={fields}
        endpoint="/lessons"
        initialValues={{ start_time: defaultStart(), duration_min: 60 }}
        transform={transform}
        renderWarnings={renderWarnings}
        submitLabel="Schedule"
        testidPrefix="lessons-add"
        onCreated={load}
      />

      {/* Mobile FAB — quick aisle-side scheduling. Hidden when no riders. */}
      {!ridersEmpty && (
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="fab lg:hidden"
          data-testid="lessons-fab"
          aria-label="Schedule lesson"
        >
          <Plus strokeWidth={1.8} className="w-7 h-7" />
        </button>
      )}
    </div>
  );
}

// Keep helper for future use (default start time).
export { defaultStart };
