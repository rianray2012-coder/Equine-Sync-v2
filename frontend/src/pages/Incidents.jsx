import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, AlertTriangle } from "lucide-react";
import { api, fmtDate, fmtTime } from "../lib/api";
import { Card, PageHeader, StatusPill, Empty } from "../components/Primitives";
import QuickAddSheet from "../components/QuickAddSheet";

const INCIDENT_TYPES = ["injury", "loose_horse", "kick", "fall", "trailer", "fence", "facility", "other"];
const SEVERITIES = ["mild", "moderate", "severe"];

function defaultOccurredAt() {
  // Local ISO without seconds → "YYYY-MM-DDTHH:mm" for the datetime-local input.
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function Incidents() {
  const [items, setItems] = useState([]);
  const [horses, setHorses] = useState([]);
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => api.get("/incidents").then((r) => setItems(r.data)), []);
  useEffect(() => {
    load();
    api.get("/horses").then((r) => setHorses(r.data));
  }, [load]);

  const horseOptions = useMemo(
    () => [
      { v: "__none__", l: "— Facility-wide (no horse) —" },
      ...horses.map((h) => ({ v: h.id, l: h.name })),
    ],
    [horses],
  );

  const fields = useMemo(() => [
    { key: "type", label: "Type", kind: "select", opts: INCIDENT_TYPES, required: true },
    { key: "severity", label: "Severity", kind: "select", opts: SEVERITIES, required: true },
    { key: "horse_id", label: "Horse", kind: "select", opts: horseOptions, full: true },
    { key: "title", label: "Title", required: true, full: true, placeholder: "Cast in stall overnight" },
    { key: "occurred_at", label: "Occurred at", type: "datetime-local", required: true, full: true },
    { key: "description", label: "What happened", required: true, kind: "textarea", rows: 4, full: true, placeholder: "Brief, factual account. Who was there, what was observed, action taken." },
    { key: "follow_up", label: "Follow-up", kind: "textarea", rows: 2, full: true, placeholder: "Optional: vet called, monitoring plan, follow-up date." },
  ], [horseOptions]);

  const transform = (form) => ({
    ...form,
    // datetime-local → ISO with seconds
    occurred_at: form.occurred_at ? new Date(form.occurred_at).toISOString() : new Date().toISOString(),
    horse_id: form.horse_id && form.horse_id !== "__none__" ? form.horse_id : null,
  });

  return (
    <div data-testid="incidents-page">
      <PageHeader
        eyebrow="Safety"
        title="Incident Reports"
        subtitle="Calm, factual record of safety events. Document quickly while the details are fresh."
        action={
          <button
            onClick={() => setAddOpen(true)}
            data-testid="incidents-add-btn"
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Report incident
          </button>
        }
      />

      {items.length === 0 ? (
        <Empty>
          <AlertTriangle strokeWidth={1.4} className="w-7 h-7 mx-auto mb-3 text-equine-amber" />
          <div className="font-display text-2xl text-equine-ivory mb-1">No incidents reported</div>
          <div className="text-[13px] text-equine-platinum/60 mb-4">A clean record is a good thing. Report any safety event — even minor — to build a trustworthy timeline.</div>
          <button onClick={() => setAddOpen(true)} data-testid="incidents-empty-add" className="btn-primary inline-flex items-center gap-2">
            <Plus className="w-4 h-4" /> Report first incident
          </button>
        </Empty>
      ) : (
        <Card hover={false}>
          {items.map((i) => (
            <div key={i.id} data-testid={`incident-${i.id}`} className="py-4 hairline">
              <div className="flex items-center justify-between gap-3 mb-1">
                <div className="font-display text-xl text-equine-ivory">{i.title}</div>
                <StatusPill tone={i.severity === "severe" ? "critical" : i.severity === "moderate" ? "warning" : "neutral"}>
                  {i.severity || "moderate"}
                </StatusPill>
              </div>
              <div className="text-[12.5px] text-equine-platinum/60">
                {fmtDate(i.occurred_at)} · {fmtTime(i.occurred_at)}
                {i.horse_name ? ` · ${i.horse_name}` : " · Facility"}
                {i.reported_by ? ` · Reported by ${i.reported_by}` : ""}
              </div>
              <div className="text-equine-silver/80 text-[14px] mt-2">{i.description}</div>
              {i.follow_up && <div className="text-[13px] text-equine-champagne mt-2">Follow-up: {i.follow_up}</div>}
            </div>
          ))}
        </Card>
      )}

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Report incident"
        eyebrow="Safety"
        fields={fields}
        endpoint="/incidents"
        initialValues={{ occurred_at: defaultOccurredAt(), severity: "moderate" }}
        transform={transform}
        submitLabel="Save report"
        testidPrefix="incidents-add"
        onCreated={load}
      />

      {/* Mobile FAB — fast in-the-moment safety logging */}
      <button
        type="button"
        onClick={() => setAddOpen(true)}
        className="fab lg:hidden"
        data-testid="incidents-fab"
        aria-label="Report incident"
      >
        <Plus strokeWidth={1.8} className="w-7 h-7" />
      </button>
    </div>
  );
}
