import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, track } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Check, ChevronRight, ChevronLeft, Upload, Plus, Trash2, Building2, MapPin, Users, Cat, GraduationCap, UtensilsCrossed, Package, UserPlus, Calendar, Rocket, Download, AlertTriangle, Copy, Send, X } from "lucide-react";
import { toast } from "sonner";
import {
  Select as ShadSelect, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";

const ICONS = {
  barn: Building2, locations: MapPin, owners: Users, horses: Cat, riders: GraduationCap,
  feed_templates: UtensilsCrossed, inventory: Package, staff: UserPlus, schedules: Calendar, review: Rocket,
};

export default function Onboarding() {
  const navigate = useNavigate();
  const [steps, setSteps] = useState([]);
  const [progress, setProgress] = useState(null);
  const [currentId, setCurrentId] = useState("barn");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get("/onboarding/steps"), api.get("/onboarding/progress")])
      .then(([s, p]) => {
        setSteps(s.data.steps);
        setProgress(p.data);
        setCurrentId(p.data.current_step || s.data.steps[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  const setStepStatus = async (step_id, status) => {
    const r = await api.patch("/onboarding/progress", { step_id, status });
    setProgress(r.data);
  };
  const setCurrent = async (step_id) => {
    setCurrentId(step_id);
    const r = await api.patch("/onboarding/progress", { current_step: step_id });
    setProgress(r.data);
  };

  const stepIndex = steps.findIndex((s) => s.id === currentId);
  const next = async () => {
    await setStepStatus(currentId, "complete");
    track("onboarding.step_completed", { step: currentId });
    if (stepIndex < steps.length - 1) setCurrent(steps[stepIndex + 1].id);
  };
  const skip = async () => {
    await setStepStatus(currentId, "skipped");
    track("onboarding.step_skipped", { step: currentId });
    if (stepIndex < steps.length - 1) setCurrent(steps[stepIndex + 1].id);
  };
  const back = () => {
    if (stepIndex > 0) setCurrent(steps[stepIndex - 1].id);
  };

  if (loading || !progress) return <div className="text-equine-platinum/60">Loading concierge…</div>;

  const current = steps[stepIndex];
  const Icon = ICONS[current?.id] || Building2;
  const percent = progress.percent || 0;

  return (
    <div data-testid="onboarding-page" className="max-w-7xl">
      <PageHeader
        eyebrow="Setup Concierge"
        title="Welcome to your barn"
        subtitle="A guided walkthrough to bring your facility online. Skip anything — autosave keeps your progress so you can return whenever you like."
        action={
          <div className="text-right">
            <div className="label-eyebrow">Setup progress</div>
            <div className="font-display text-3xl text-equine-champagne mt-1">{percent}%</div>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Stepper */}
        <Card hover={false} className="lg:col-span-1 !p-3 self-start sticky top-24">
          <div className="px-3 py-2">
            <div className="h-1.5 rounded-full bg-equine-soft overflow-hidden">
              <div className="h-full bg-equine-champagne transition-all duration-500" style={{ width: `${percent}%` }} />
            </div>
          </div>
          <ul className="mt-2">
            {steps.map((s, i) => {
              const Ic = ICONS[s.id] || Building2;
              const status = progress.steps?.[s.id] || "pending";
              const isCurrent = s.id === currentId;
              const isDone = status === "complete";
              const isSkipped = status === "skipped";
              return (
                <li key={s.id}>
                  <button
                    onClick={() => setCurrent(s.id)}
                    data-testid={`step-nav-${s.id}`}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
                      isCurrent ? "bg-equine-steel/30 border border-equine-steel/40 text-equine-ivory" : "hover:bg-equine-soft text-equine-silver/80"
                    }`}
                  >
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] border ${
                      isDone ? "bg-equine-sage/20 border-equine-sage text-equine-sage"
                      : isSkipped ? "bg-equine-soft border-equine-graphite text-equine-platinum/60"
                      : isCurrent ? "bg-equine-champagne text-equine-black border-equine-champagne"
                      : "bg-equine-soft border-equine-graphite/60 text-equine-platinum/60"
                    }`}>
                      {isDone ? <Check className="w-3.5 h-3.5" /> : <Ic className="w-3.5 h-3.5" />}
                    </div>
                    <span className="text-[13px] flex-1 text-left">{s.label}</span>
                    {!s.required && <span className="text-[9px] tracking-[0.18em] uppercase text-equine-platinum/50">opt</span>}
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="hairline mt-2 pt-3 px-3 pb-1 text-[11px] text-equine-platinum/60">
            Autosave on · You can leave & resume any time.
          </div>
        </Card>

        {/* Content */}
        <div className="lg:col-span-3">
          <Card hover={false}>
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-equine-steel/25 border border-equine-steel/40 flex items-center justify-center">
                <Icon strokeWidth={1.4} className="text-equine-champagne" />
              </div>
              <div className="flex-1">
                <div className="label-eyebrow">Step {stepIndex + 1} of {steps.length}</div>
                <h2 className="font-display text-3xl text-equine-ivory mt-1">{current?.label}</h2>
              </div>
              <StatusPill tone={progress.steps?.[currentId] === "complete" ? "success" : progress.steps?.[currentId] === "skipped" ? "neutral" : "info"}>
                {progress.steps?.[currentId] || "pending"}
              </StatusPill>
            </div>

            <StepContent stepId={currentId} onAnyChange={() => setStepStatus(currentId, "in_progress")} onFinish={() => navigate("/")} />

            <div className="mt-8 pt-6 hairline flex items-center justify-between">
              <button onClick={back} disabled={stepIndex === 0} data-testid="step-back" className="btn-secondary disabled:opacity-40 inline-flex items-center gap-2">
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
              <div className="flex items-center gap-2">
                {!current?.required && (
                  <button onClick={skip} data-testid="step-skip" className="btn-secondary">Skip for now</button>
                )}
                {currentId === "review" ? (
                  <button
                    data-testid="step-finish"
                    onClick={async () => {
                      await setStepStatus("review", "complete");
                      await api.post("/onboarding/complete");
                      track("onboarding.completed", { percent: 100 });
                      toast.success("Barn setup complete!");
                      navigate("/");
                    }}
                    className="btn-primary inline-flex items-center gap-2"
                  >
                    Launch barn <Rocket className="w-4 h-4" />
                  </button>
                ) : (
                  <button onClick={next} data-testid="step-next" className="btn-primary inline-flex items-center gap-2">
                    Save & continue <ChevronRight className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ============== Step content router ==============
function StepContent({ stepId, onAnyChange, onFinish }) {
  if (stepId === "barn") return <BarnStep onAnyChange={onAnyChange} />;
  if (stepId === "locations") return <CrudStep kind="locations" onAnyChange={onAnyChange} />;
  if (stepId === "owners") return <OwnersStep onAnyChange={onAnyChange} />;
  if (stepId === "horses") return <HorsesStep onAnyChange={onAnyChange} />;
  if (stepId === "riders") return <RidersStep onAnyChange={onAnyChange} />;
  if (stepId === "feed_templates") return <CrudStep kind="feed_templates" onAnyChange={onAnyChange} />;
  if (stepId === "inventory") return <CrudStep kind="inventory" onAnyChange={onAnyChange} />;
  if (stepId === "staff") return <StaffStep onAnyChange={onAnyChange} />;
  if (stepId === "schedules") return <CrudStep kind="schedules" onAnyChange={onAnyChange} />;
  if (stepId === "review") return <ReviewStep />;
  return null;
}

// ============== Step 1: Barn ==============
function BarnStep({ onAnyChange }) {
  const [barn, setBarn] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/barn").then((r) => setBarn(r.data)); }, []);
  const update = (patch) => { setBarn({ ...barn, ...patch }); onAnyChange(); };

  const save = async () => {
    setSaving(true);
    try { await api.put("/barn", barn); toast.success("Barn profile saved"); }
    catch { toast.error("Save failed"); }
    finally { setSaving(false); }
  };

  if (!barn) return <div className="text-equine-platinum/60">Loading…</div>;

  return (
    <div className="space-y-5" data-testid="step-barn">
      <p className="text-equine-silver/70 text-[14px]">Tell us about your facility. This drives branding, timezone-aware schedules and contact details for owners.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Barn name" value={barn.name} onChange={(v) => update({ name: v })} placeholder="Whitfield Equestrian Estate" testid="barn-name" />
        <Select label="Facility type" value={barn.facility_type} onChange={(v) => update({ facility_type: v })} options={[
          { v: "private", l: "Private" }, { v: "boarding", l: "Boarding" }, { v: "lesson", l: "Lesson Program" },
          { v: "training", l: "Training" }, { v: "show", l: "Show Barn" }, { v: "rehab", l: "Rehab Facility" }, { v: "rescue", l: "Rescue" },
        ]} testid="barn-type" />
        <Field label="Address" value={barn.address} onChange={(v) => update({ address: v })} placeholder="1200 Whitfield Lane, Wellington FL" testid="barn-address" />
        <Field label="Timezone" value={barn.timezone} onChange={(v) => update({ timezone: v })} placeholder="America/New_York" testid="barn-tz" />
        <Field label="Contact email" type="email" value={barn.contact_email} onChange={(v) => update({ contact_email: v })} placeholder="ops@whitfield.com" testid="barn-email" />
        <Field label="Contact phone" value={barn.contact_phone} onChange={(v) => update({ contact_phone: v })} placeholder="+1 555 0100" testid="barn-phone" />
        <Field label="Logo URL" value={barn.logo_url} onChange={(v) => update({ logo_url: v })} placeholder="https://…" testid="barn-logo" />
        <Field label="Disciplines (comma-sep)" value={(barn.disciplines || []).join(", ")} onChange={(v) => update({ disciplines: v.split(",").map(s => s.trim()).filter(Boolean) })} placeholder="Show Jumping, Dressage, Hunters" testid="barn-disc" />
      </div>
      <button onClick={save} disabled={saving} className="btn-primary" data-testid="barn-save">{saving ? "Saving…" : "Save profile"}</button>
    </div>
  );
}

// ============== Locations / Feed Templates / Inventory / Schedules (generic CRUD) ==============
const CRUD_CONFIG = {
  locations: {
    endpoint: "/locations",
    title: "Map your facility",
    desc: "Add stalls, paddocks, pastures, arenas, tack rooms — every named place that operations depend on.",
    fields: [
      { key: "type", label: "Type", kind: "select", opts: ["stall", "paddock", "pasture", "arena", "tack_room", "feed_room", "wash_rack"], required: true },
      { key: "name", label: "Name", placeholder: "Stall 12 / North Pasture", required: true },
      { key: "capacity", label: "Capacity", type: "number" },
      { key: "notes", label: "Notes" },
    ],
    display: (r) => `${r.type.replace('_', ' ')} · ${r.name}${r.capacity ? ` · cap ${r.capacity}` : ""}`,
  },
  feed_templates: {
    endpoint: "/feed-templates",
    title: "Feed templates",
    desc: "Standard rations applied across the barn. Per-horse customisations can be added later in each horse profile.",
    fields: [
      { key: "meal", label: "Meal", kind: "select", opts: ["morning", "midday", "evening"], required: true },
      { key: "hay_type", label: "Hay type", placeholder: "Timothy / Alfalfa mix" },
      { key: "hay_lbs", label: "Hay (lbs)", type: "number" },
      { key: "grain_type", label: "Grain type", placeholder: "Triple Crown Senior" },
      { key: "grain_lbs", label: "Grain (lbs)", type: "number" },
      { key: "supplements", label: "Supplements" },
      { key: "med_timing", label: "Medication timing" },
      { key: "instructions", label: "Instructions" },
    ],
    display: (r) => `${r.meal} · ${r.grain_lbs || 0}lb grain · ${r.hay_lbs || 0}lb hay${r.supplements ? ` · ${r.supplements}` : ""}`,
  },
  inventory: {
    endpoint: "/inventory",
    title: "Starting inventory",
    desc: "Track grain, hay, bedding, supplements and medical supplies. Set reorder thresholds for automatic low-stock alerts.",
    fields: [
      { key: "category", label: "Category", kind: "select", opts: ["grain", "hay", "bedding", "supplements", "medical", "blankets", "tack", "other"], required: true },
      { key: "name", label: "Item", placeholder: "Triple Crown Senior", required: true },
      { key: "quantity", label: "On hand", type: "number" },
      { key: "unit", label: "Unit", placeholder: "lbs / bales / count" },
      { key: "reorder_at", label: "Reorder at", type: "number" },
      { key: "vendor", label: "Vendor" },
      { key: "cost_per_unit", label: "Cost / unit", type: "number" },
    ],
    display: (r) => `${r.category} · ${r.name} · ${r.quantity || 0} ${r.unit || ""}${r.low_stock ? " · LOW" : ""}`,
  },
  schedules: {
    endpoint: "/recurring-schedules",
    title: "Recurring schedules",
    desc: "Standing routines: turnout rotations, med rounds, blanketing, lesson blocks. These power the daily Barn Board.",
    fields: [
      { key: "type", label: "Type", kind: "select", opts: ["turnout", "feed", "medication", "blanketing", "lesson_block", "training_ride"], required: true },
      { key: "name", label: "Name", placeholder: "Morning turnout — Geldings A", required: true },
      { key: "time", label: "Time", placeholder: "07:30" },
      { key: "days_of_week", label: "Days (comma-sep)", placeholder: "mon, tue, wed, thu, fri", kind: "csv" },
      { key: "notes", label: "Notes" },
    ],
    display: (r) => `${r.type.replace('_', ' ')} · ${r.name} · ${r.time || ""} · ${(r.days_of_week || []).join("/")}`,
  },
};

function CrudStep({ kind, onAnyChange }) {
  const cfg = CRUD_CONFIG[kind];
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const load = () => api.get(cfg.endpoint).then((r) => setItems(r.data));
  useEffect(() => { load(); }, [kind]);

  const updateForm = (k, v) => { setForm({ ...form, [k]: v }); onAnyChange(); };

  const submit = async (e) => {
    e.preventDefault();
    const required = cfg.fields.filter((f) => f.required).map((f) => f.key);
    for (const k of required) if (!form[k]) { toast.error(`${k} is required`); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      cfg.fields.forEach((f) => {
        if (f.kind === "csv" && typeof payload[f.key] === "string") {
          payload[f.key] = payload[f.key].split(",").map(s => s.trim()).filter(Boolean);
        }
        if (f.type === "number" && payload[f.key] !== undefined && payload[f.key] !== "") {
          payload[f.key] = Number(payload[f.key]);
        }
      });
      await api.post(cfg.endpoint, payload);
      setForm({});
      load();
      toast.success("Added");
    } catch (e) { toast.error("Failed to add"); }
    finally { setSaving(false); }
  };

  const remove = async (id) => { await api.delete(`${cfg.endpoint}/${id}`); load(); };

  return (
    <div data-testid={`step-${kind}`}>
      <p className="text-equine-silver/70 text-[14px] mb-5">{cfg.desc}</p>
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {cfg.fields.map((f) => {
          if (f.kind === "select") {
            return <Select key={f.key} label={f.label} value={form[f.key] || ""} onChange={(v) => updateForm(f.key, v)} options={f.opts.map((o) => ({ v: o, l: o.replace('_', ' ') }))} testid={`${kind}-${f.key}`} />;
          }
          return <Field key={f.key} label={f.label} type={f.type} value={form[f.key] || ""} onChange={(v) => updateForm(f.key, v)} placeholder={f.placeholder} testid={`${kind}-${f.key}`} />;
        })}
        <div className="md:col-span-2">
          <button disabled={saving} className="btn-primary inline-flex items-center gap-2" data-testid={`${kind}-add`}>
            <Plus className="w-4 h-4" /> {saving ? "Adding…" : "Add"}
          </button>
        </div>
      </form>

      <div className="label-eyebrow mb-2">Existing · {items.length}</div>
      <div className="space-y-2">
        {items.length === 0 && <div className="text-equine-platinum/60 text-sm py-4">None yet — add your first above.</div>}
        {items.map((it) => (
          <div key={it.id} className="flex items-center justify-between py-3 px-4 rounded-lg bg-equine-soft border border-equine-graphite/40">
            <div className="text-[13.5px] text-equine-silver capitalize">{cfg.display(it)}</div>
            <button onClick={() => remove(it.id)} data-testid={`${kind}-remove-${it.id}`} className="text-equine-platinum/60 hover:text-equine-clay p-1.5 rounded">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============== Owners / Horses (with CSV) ==============
function OwnersStep({ onAnyChange }) {
  return <RecordsWithCsvStep kind="owners" endpoint="/owners" displayKey="full_name" onAnyChange={onAnyChange}
    fields={[
      { key: "full_name", label: "Full name", required: true, placeholder: "Charlotte Vance" },
      { key: "email", label: "Email", type: "email", placeholder: "charlotte@example.com" },
      { key: "phone", label: "Phone", placeholder: "+1 555 0142" },
      { key: "emergency_contact", label: "Emergency contact" },
      { key: "billing_preferences", label: "Billing preference", kind: "select", opts: ["monthly_card", "monthly_ach", "invoice_check", "wire"] },
      { key: "waiver_signed", label: "Liability waiver signed", kind: "select", opts: ["yes", "no"] },
    ]}
    intro="Add your boarding/training clients. Or import a roster via CSV in seconds."
  />;
}

function HorsesStep({ onAnyChange }) {
  return <RecordsWithCsvStep kind="horses" endpoint="/horses" displayKey="name" onAnyChange={onAnyChange}
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
    intro="Each horse needs a profile. Add manually for elite-care detail, or upload a CSV for fast bulk import."
  />;
}

function RidersStep({ onAnyChange }) {
  return <RecordsWithCsvStep kind="riders" endpoint="/riders" displayKey="full_name" onAnyChange={onAnyChange} noCsv
    fields={[
      { key: "full_name", label: "Rider name", required: true },
      { key: "age", label: "Age", type: "number" },
      { key: "skill_level", label: "Skill level", kind: "select", opts: ["beginner", "intermediate", "advanced"] },
      { key: "goals", label: "Goals / competition focus" },
      { key: "emergency_contact", label: "Emergency contact" },
    ]}
    intro="Track riders and their development goals. Connect riders to lesson packages and trainers."
  />;
}

function RecordsWithCsvStep({ kind, endpoint, displayKey, fields, intro, noCsv, onAnyChange }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);
  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const fileRef = useRef();

  const load = () => api.get(endpoint).then((r) => setItems(r.data));
  useEffect(() => { load(); }, [kind]);

  const submit = async (e) => {
    e.preventDefault();
    for (const f of fields) if (f.required && !form[f.key]) { toast.error(`${f.label} required`); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      fields.forEach((f) => {
        if (f.type === "number" && payload[f.key] !== "") payload[f.key] = Number(payload[f.key]);
      });
      await api.post(endpoint, payload);
      setForm({}); load();
      toast.success("Added");
    } catch (e) { toast.error("Failed"); }
    finally { setSaving(false); }
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
    } finally { setPreviewing(false); }
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
    const a = document.createElement("a"); a.href = url; a.download = r.data.filename; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div data-testid={`step-${kind}`}>
      <div className="flex items-start justify-between gap-4 mb-5">
        <p className="text-equine-silver/70 text-[14px] flex-1">{intro}</p>
        {!noCsv && (
          <div className="flex gap-2">
            <button onClick={downloadTemplate} data-testid={`${kind}-csv-template`} className="btn-secondary !py-1.5 !px-3 text-[12px] inline-flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Template</button>
            <button onClick={() => setCsvOpen(!csvOpen)} data-testid={`${kind}-csv-toggle`} className="btn-primary !py-1.5 !px-3 text-[12px] inline-flex items-center gap-1.5"><Upload className="w-3.5 h-3.5" /> {csvOpen ? "Close" : "CSV import"}</button>
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
            Drag & drop a .csv file or paste content. Headers should match the downloadable template above.
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
                      <span className="text-equine-amber text-[11px] inline-flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {preview.duplicates.length} duplicate{preview.duplicates.length > 1 ? "s" : ""}</span>
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
          <Select key={f.key} label={f.label} value={form[f.key] || ""} onChange={(v) => { setForm({ ...form, [f.key]: v }); onAnyChange(); }}
            options={f.opts.map((o) => ({ v: o, l: o.replace('_', ' ') }))} testid={`${kind}-${f.key}`} />
        ) : (
          <Field key={f.key} label={f.label} type={f.type} placeholder={f.placeholder} value={form[f.key] || ""}
            onChange={(v) => { setForm({ ...form, [f.key]: v }); onAnyChange(); }} testid={`${kind}-${f.key}`} />
        ))}
        <div className="md:col-span-2">
          <button disabled={saving} className="btn-primary inline-flex items-center gap-2" data-testid={`${kind}-add`}>
            <Plus className="w-4 h-4" /> {saving ? "Adding…" : `Add ${kind.slice(0, -1)}`}
          </button>
        </div>
      </form>

      <div className="label-eyebrow mb-2">Roster · {items.length}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {items.length === 0 && <div className="text-equine-platinum/60 text-sm py-4 md:col-span-2">No records yet.</div>}
        {items.map((it) => (
          <div key={it.id} className="px-4 py-2.5 rounded-lg bg-equine-soft border border-equine-graphite/40 text-equine-silver text-[13.5px]">
            {it[displayKey]}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============== Staff invites (magic-link) ==============
function StaffStep({ onAnyChange }) {
  const [invites, setInvites] = useState([]);
  const [form, setForm] = useState({ email: "", full_name: "", role: "trainer" });
  const [sending, setSending] = useState(false);
  const [lastDevLink, setLastDevLink] = useState(null);

  const load = () => api.get("/invites").then((r) => setInvites(r.data)).catch(() => setInvites([]));
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.role) { toast.error("Email and role required"); return; }
    setSending(true);
    try {
      const r = await api.post("/invites", form);
      toast.success("Invitation sent");
      if (r.data.dev_accept_url) setLastDevLink({ url: r.data.dev_accept_url, email: form.email });
      else setLastDevLink(null);
      setForm({ email: "", full_name: "", role: "trainer" });
      load();
      onAnyChange();
      track("onboarding.invite_sent", { role: r.data.role });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send invitation");
    } finally { setSending(false); }
  };

  const resend = async (id) => {
    try {
      const r = await api.post(`/invites/${id}/resend`);
      toast.success("Reminder sent");
      if (r.data.dev_accept_url) setLastDevLink({ url: r.data.dev_accept_url, email: r.data.email });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const revoke = async (id) => {
    if (!window.confirm("Revoke this invitation?")) return;
    await api.post(`/invites/${id}/revoke`);
    toast.success("Invitation revoked");
    load();
  };

  const copy = (text) => { navigator.clipboard?.writeText(text); toast.success("Link copied"); };

  return (
    <div data-testid="step-staff">
      <p className="text-equine-silver/70 text-[14px] mb-5">
        Invite barn managers, trainers, grooms, vets, parents and owners. Each invitee receives a private magic link to set their password — no signups required.
        Roles with setup permissions (Owner / Barn Manager) will be guided through this concierge automatically on first login.
      </p>

      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <Field label="Full name" value={form.full_name} onChange={(v) => setForm({ ...form, full_name: v })} testid="staff-name" placeholder="Marcus Aldridge" />
        <Field label="Email" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} testid="staff-email" placeholder="marcus@…" />
        <Select label="Role" value={form.role} onChange={(v) => setForm({ ...form, role: v })} testid="staff-role"
          options={[
            { v: "barn_manager", l: "Barn Manager" }, { v: "trainer", l: "Trainer" }, { v: "groom", l: "Groom" },
            { v: "working_student", l: "Working Student" }, { v: "horse_owner", l: "Horse Owner" }, { v: "parent", l: "Parent / Guardian" },
            { v: "veterinarian", l: "Veterinarian" }, { v: "farrier", l: "Farrier" }, { v: "admin", l: "Admin" },
          ]}
        />
        <div className="md:col-span-3">
          <button disabled={sending} className="btn-primary inline-flex items-center gap-2" data-testid="staff-invite">
            <Send className="w-4 h-4" /> {sending ? "Sending…" : "Send invitation"}
          </button>
        </div>
      </form>

      {lastDevLink && (
        <div className="mb-5 p-4 rounded-xl bg-equine-amber/10 border border-equine-amber/40" data-testid="dev-link-banner">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-equine-amber mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[12.5px] text-equine-amber font-medium mb-1">Email delivery is in dev mode</div>
              <div className="text-[12px] text-equine-platinum/70 mb-2">
                Add a Resend API key to backend/.env to enable real email. For now, copy this magic link and share it with <strong className="text-equine-ivory">{lastDevLink.email}</strong>:
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate bg-equine-card px-3 py-2 rounded-lg text-[11.5px] text-equine-champagne font-mono">{lastDevLink.url}</code>
                <button onClick={() => copy(lastDevLink.url)} className="btn-secondary !py-1.5 !px-3 text-[12px] inline-flex items-center gap-1"><Copy className="w-3.5 h-3.5" /> Copy</button>
              </div>
            </div>
            <button onClick={() => setLastDevLink(null)} className="text-equine-platinum/60 hover:text-equine-ivory"><X className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      <div className="label-eyebrow mb-2">Sent invitations · {invites.length}</div>
      <div className="space-y-2">
        {invites.length === 0 && <div className="text-equine-platinum/60 text-sm py-3">No invitations yet.</div>}
        {invites.map((iv) => {
          const tone = iv.status === "accepted" ? "success"
            : iv.status === "revoked" || iv.status === "expired" ? "neutral"
            : "info";
          return (
            <div key={iv.id} className="flex items-center gap-3 py-3 px-4 rounded-lg bg-equine-soft border border-equine-graphite/40">
              <div className="flex-1 min-w-0">
                <div className="text-equine-silver text-[13.5px] truncate">{iv.full_name || iv.email}</div>
                <div className="text-[11.5px] text-equine-platinum/60 capitalize truncate">{iv.role.replace('_', ' ')} · {iv.email}</div>
              </div>
              <StatusPill tone={tone}>{iv.status}</StatusPill>
              {iv.status === "pending" && (
                <>
                  <button onClick={() => resend(iv.id)} data-testid={`invite-resend-${iv.id}`} className="text-equine-platinum/60 hover:text-equine-champagne p-1.5" title="Resend"><Send className="w-4 h-4" /></button>
                  <button onClick={() => revoke(iv.id)} data-testid={`invite-revoke-${iv.id}`} className="text-equine-platinum/60 hover:text-equine-clay p-1.5" title="Revoke"><Trash2 className="w-4 h-4" /></button>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============== Review ==============
function ReviewStep() {
  const [data, setData] = useState(null);
  useEffect(() => {
    Promise.all([
      api.get("/barn"), api.get("/locations"), api.get("/owners"), api.get("/horses"),
      api.get("/riders"), api.get("/feed-templates"), api.get("/inventory"),
      api.get("/invites").catch(() => ({ data: [] })), api.get("/recurring-schedules"),
    ]).then(([barn, locations, owners, horses, riders, feeds, inv, staff, sched]) => {
      setData({ barn: barn.data, locations: locations.data, owners: owners.data, horses: horses.data,
        riders: riders.data, feeds: feeds.data, inv: inv.data, staff: staff.data, sched: sched.data });
    });
  }, []);
  if (!data) return <div className="text-equine-platinum/60">Loading review…</div>;

  const summary = [
    { label: "Locations", value: data.locations.length, hint: "stalls / paddocks / arenas" },
    { label: "Owners", value: data.owners.length, hint: "clients" },
    { label: "Horses", value: data.horses.length, hint: "active in barn" },
    { label: "Riders", value: data.riders.length, hint: "active program" },
    { label: "Feed templates", value: data.feeds.length, hint: "daily meals" },
    { label: "Inventory items", value: data.inv.length, hint: "tracked stock" },
    { label: "Staff invites", value: data.staff.length, hint: "team" },
    { label: "Recurring schedules", value: data.sched.length, hint: "routines" },
  ];

  return (
    <div data-testid="step-review">
      <p className="text-equine-silver/70 text-[14px] mb-5">Final review before launching daily operations. You can continue adding records anytime from each module.</p>
      <div className="mb-5">
        <div className="label-eyebrow mb-1">Barn</div>
        <div className="font-display text-2xl text-equine-ivory">{data.barn.name || "Unnamed barn"}</div>
        <div className="text-[13px] text-equine-platinum/70 mt-0.5">
          {data.barn.facility_type} · {data.barn.address || "—"} · {data.barn.timezone}
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {summary.map((s) => (
          <div key={s.label} className="rounded-xl bg-equine-soft border border-equine-graphite/40 p-4">
            <div className="label-eyebrow">{s.label}</div>
            <div className="font-display text-3xl text-equine-ivory mt-1">{s.value}</div>
            <div className="text-[11.5px] text-equine-platinum/60 mt-0.5">{s.hint}</div>
          </div>
        ))}
      </div>
      <div className="mt-6 p-4 rounded-xl bg-equine-steel/15 border border-equine-steel/40">
        <div className="text-equine-ivory text-[14px] font-medium mb-1">You're ready to ride.</div>
        <div className="text-[12.5px] text-equine-platinum/70">Click <span className="text-equine-champagne">Launch barn</span> to mark setup complete. Daily operations, feed cards, and the barn board will reflect everything you configured above.</div>
      </div>
    </div>
  );
}

// ============== form primitives ==============
const Field = ({ label, value, onChange, placeholder, type = "text", testid }) => (
  <label className="block">
    <div className="label-eyebrow mb-1.5">{label}</div>
    <input
      type={type} value={value || ""} onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder} data-testid={testid}
      className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory focus:border-equine-champagne outline-none text-[14px] transition-colors"
    />
  </label>
);

const Select = ({ label, value, onChange, options, testid }) => (
  <label className="block">
    <div className="label-eyebrow mb-1.5">{label}</div>
    <ShadSelect value={value || ""} onValueChange={(v) => onChange(v)}>
      <SelectTrigger data-testid={testid}
        className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory hover:border-equine-graphite focus:border-equine-champagne text-[14px] h-auto">
        <SelectValue placeholder="Choose…" />
      </SelectTrigger>
      <SelectContent className="bg-equine-card border-equine-graphite/60 text-equine-ivory">
        {options.map((o) => (
          <SelectItem key={o.v} value={o.v} className="capitalize focus:bg-equine-soft focus:text-equine-ivory">
            {o.l}
          </SelectItem>
        ))}
      </SelectContent>
    </ShadSelect>
  </label>
);
