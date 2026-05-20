import React, { useEffect, useRef, useState } from "react";
import { api, track } from "../../lib/api";
import { toast } from "sonner";
import { Card } from "../Primitives";
import { Plus, Trash2, Upload, Download, AlertTriangle } from "lucide-react";
import { Field, Select } from "./FormPrimitives";

/**
 * Records-with-CSV step — owners + horses (which support bulk CSV import).
 * Rider step reuses this with noCsv=true.
 *
 * Behaviour preserved exactly from the original Onboarding.jsx: paste-or-upload,
 * preview before commit, duplicate flagging, template download, individual add form.
 */
const RecordsWithCsvStep = ({ kind, endpoint, displayKey, fields, intro, noCsv, onAnyChange }) => {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);
  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const fileRef = useRef();

  const load = () => api.get(endpoint).then((r) => setItems(r.data));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [kind]);

  const submit = async (e) => {
    e.preventDefault();
    for (const f of fields) {
      if (f.required && !form[f.key]) { toast.error(`${f.label} required`); return; }
    }
    setSaving(true);
    try {
      const payload = { ...form };
      fields.forEach((f) => {
        if (f.type === "number" && payload[f.key] !== "") payload[f.key] = Number(payload[f.key]);
      });
      await api.post(endpoint, payload);
      setForm({}); load();
      toast.success("Added");
    } catch {
      toast.error("Failed");
    } finally {
      setSaving(false);
    }
  };

  const handleFile = async (file) => {
    if (!file) return;
    const text = await file.text();
    setCsvText(text);
  };

  const doPreview = async () => {
    if (!csvText.trim()) { toast.error("Paste or upload a CSV first"); return; }
    setPreviewing(true);
    try {
      const r = await api.post("/onboarding/csv-preview", { kind, csv_text: csvText });
      setPreview(r.data);
      onAnyChange();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "CSV parse failed");
    } finally {
      setPreviewing(false);
    }
  };

  const doCommit = async () => {
    if (!preview?.rows?.length) return;
    const r = await api.post("/onboarding/csv-commit", { kind, rows: preview.rows });
    toast.success(`Imported ${r.data.created} ${kind}${r.data.skipped ? ` · ${r.data.skipped} skipped (duplicates)` : ""}`);
    track("onboarding.csv_imported", { kind, created: r.data.created, skipped: r.data.skipped });
    setCsvOpen(false); setCsvText(""); setPreview(null);
    load();
  };

  const downloadTemplate = async () => {
    const r = await api.get(`/onboarding/csv-template?kind=${kind}`);
    const blob = new Blob([r.data.text], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = r.data.filename; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid={`step-${kind}`}>
      <div className="flex items-start justify-between gap-4 mb-5">
        <p className="text-equine-silver/70 text-[14px] flex-1">{intro}</p>
        {!noCsv && (
          <div className="flex gap-2">
            <button onClick={downloadTemplate} data-testid={`${kind}-csv-template`} className="btn-secondary !py-1.5 !px-3 text-[12px] inline-flex items-center gap-1.5">
              <Download className="w-3.5 h-3.5" /> Template
            </button>
            <button onClick={() => setCsvOpen(!csvOpen)} data-testid={`${kind}-csv-toggle`} className="btn-primary !py-1.5 !px-3 text-[12px] inline-flex items-center gap-1.5">
              <Upload className="w-3.5 h-3.5" /> {csvOpen ? "Close" : "CSV import"}
            </button>
          </div>
        )}
      </div>

      {csvOpen && (
        <Card hover={false} className="!bg-equine-soft mb-5 border-equine-steel/40">
          <div className="flex items-center gap-3 mb-3">
            <Upload strokeWidth={1.4} className="text-equine-champagne" />
            <div className="font-display text-xl">Bulk import via CSV</div>
          </div>
          <div className="text-[12.5px] text-equine-platinum/70 mb-3">
            Drag &amp; drop a .csv file or paste content. Headers should match the downloadable template above.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <input
                type="file" accept=".csv,text/csv"
                ref={fileRef}
                data-testid={`${kind}-csv-file`}
                onChange={(e) => handleFile(e.target.files?.[0])}
                className="block w-full text-[12.5px] text-equine-silver/80 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border file:border-equine-graphite file:bg-equine-card file:text-equine-ivory hover:file:bg-equine-tertiary file:cursor-pointer cursor-pointer"
              />
              <textarea
                value={csvText} onChange={(e) => setCsvText(e.target.value)}
                placeholder="…or paste CSV text here"
                rows={6}
                data-testid={`${kind}-csv-text`}
                className="mt-3 w-full bg-equine-card border border-equine-graphite/60 rounded-lg px-3 py-2 text-[12.5px] font-mono text-equine-silver focus:border-equine-champagne outline-none"
              />
            </div>
            <div>
              {preview ? (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="label-eyebrow">Preview · {preview.count} rows</div>
                    {preview.duplicates.length > 0 && (
                      <span className="text-equine-amber text-[11px] inline-flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> {preview.duplicates.length} duplicate{preview.duplicates.length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <div className="max-h-48 overflow-y-auto scrollbar-luxe rounded-lg border border-equine-graphite/40 divide-y divide-equine-graphite/30">
                    {preview.rows.slice(0, 10).map((r, i) => (
                      <div key={i} className="px-3 py-1.5 text-[12px] text-equine-silver/90 truncate">
                        {r.name || r.full_name || JSON.stringify(r).slice(0, 60)}
                      </div>
                    ))}
                  </div>
                  <button onClick={doCommit} data-testid={`${kind}-csv-commit`} className="btn-primary w-full mt-3 inline-flex items-center justify-center gap-2">
                    Import {preview.count} {kind}
                  </button>
                </div>
              ) : (
                <button onClick={doPreview} disabled={previewing} data-testid={`${kind}-csv-preview`} className="btn-secondary w-full">
                  {previewing ? "Parsing…" : "Preview import"}
                </button>
              )}
            </div>
          </div>
        </Card>
      )}

      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {fields.map((f) => f.kind === "select" ? (
          <Select
            key={f.key}
            label={f.label}
            value={form[f.key] || ""}
            onChange={(v) => { setForm({ ...form, [f.key]: v }); onAnyChange(); }}
            options={f.opts.map((o) => ({ v: o, l: o.replace("_", " ") }))}
            testid={`${kind}-${f.key}`}
          />
        ) : (
          <Field
            key={f.key}
            label={f.label}
            type={f.type}
            placeholder={f.placeholder}
            value={form[f.key] || ""}
            onChange={(v) => { setForm({ ...form, [f.key]: v }); onAnyChange(); }}
            testid={`${kind}-${f.key}`}
          />
        ))}
        <div className="md:col-span-2">
          <button disabled={saving} className="btn-primary inline-flex items-center gap-2" data-testid={`${kind}-add`}>
            <Plus className="w-4 h-4" /> {saving ? "Adding…" : `Add ${kind.slice(0, -1)}`}
          </button>
        </div>
      </form>

      <div className="label-eyebrow mb-2">Roster · {items.length}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {items.length === 0 && (
          <div className="text-equine-platinum/60 text-sm py-4 md:col-span-2">No records yet.</div>
        )}
        {items.map((it) => (
          <div key={it.id} className="px-4 py-2.5 rounded-lg bg-equine-soft border border-equine-graphite/40 text-equine-silver text-[13.5px]">
            {it[displayKey]}
          </div>
        ))}
      </div>
    </div>
  );
};

// ─────────── Convenience wrappers for each record type ───────────

export const OwnersStep = ({ onAnyChange }) => (
  <RecordsWithCsvStep
    kind="owners" endpoint="/owners" displayKey="full_name" onAnyChange={onAnyChange}
    intro="Add your boarding/training clients. Or import a roster via CSV in seconds."
    fields={[
      { key: "full_name", label: "Full name", required: true, placeholder: "Charlotte Vance" },
      { key: "email", label: "Email", type: "email", placeholder: "charlotte@example.com" },
      { key: "phone", label: "Phone", placeholder: "+1 555 0142" },
      { key: "emergency_contact", label: "Emergency contact" },
      { key: "billing_preferences", label: "Billing preference", kind: "select",
        opts: ["monthly_card", "monthly_ach", "invoice_check", "wire"] },
      { key: "waiver_signed", label: "Liability waiver signed", kind: "select", opts: ["yes", "no"] },
    ]}
  />
);

export const HorsesStep = ({ onAnyChange }) => (
  <RecordsWithCsvStep
    kind="horses" endpoint="/horses" displayKey="name" onAnyChange={onAnyChange}
    intro="Each horse needs a profile. Add manually for elite-care detail, or upload a CSV for fast bulk import."
    fields={[
      { key: "name", label: "Show name", required: true, placeholder: "Valentino" },
      { key: "barn_name", label: "Barn name", placeholder: "Val" },
      { key: "breed", label: "Breed", placeholder: "Hanoverian" },
      { key: "age", label: "Age", type: "number" },
      { key: "color", label: "Color" },
      { key: "height_hands", label: "Height (hh)", type: "number" },
      { key: "discipline", label: "Discipline", placeholder: "Show Jumping" },
      { key: "stall", label: "Stall / Location", placeholder: "Stall 1" },
      { key: "turnout_group", label: "Turnout group" },
      { key: "feed_plan", label: "Feed notes" },
    ]}
  />
);

export const RidersStep = ({ onAnyChange }) => (
  <RecordsWithCsvStep
    kind="riders" endpoint="/riders" displayKey="full_name" onAnyChange={onAnyChange} noCsv
    intro="Track riders and their development goals. Connect riders to lesson packages and trainers."
    fields={[
      { key: "full_name", label: "Rider name", required: true },
      { key: "age", label: "Age", type: "number" },
      { key: "skill_level", label: "Skill level", kind: "select", opts: ["beginner", "intermediate", "advanced"] },
      { key: "goals", label: "Goals / competition focus" },
      { key: "emergency_contact", label: "Emergency contact" },
    ]}
  />
);

export default RecordsWithCsvStep;
