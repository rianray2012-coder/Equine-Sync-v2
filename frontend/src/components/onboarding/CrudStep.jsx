import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { Field, Select } from "./FormPrimitives";

/**
 * Generic CRUD step (Locations / Feed templates / Inventory / Schedules).
 * Configuration lives in CRUD_CONFIG below — adding a new step is a
 * matter of declaring fields + a display formatter.
 */
const CRUD_CONFIG = {
  locations: {
    endpoint: "/locations",
    desc: "Add stalls, paddocks, pastures, arenas, tack rooms — every named place that operations depend on.",
    fields: [
      { key: "type", label: "Type", kind: "select",
        opts: ["stall", "paddock", "pasture", "arena", "tack_room", "feed_room", "wash_rack"], required: true },
      { key: "name", label: "Name", placeholder: "Stall 12 / North Pasture", required: true },
      { key: "capacity", label: "Capacity", type: "number" },
      { key: "notes", label: "Notes" },
    ],
    display: (r) => `${r.type.replace("_", " ")} · ${r.name}${r.capacity ? ` · cap ${r.capacity}` : ""}`,
  },
  feed_templates: {
    endpoint: "/feed-templates",
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
    desc: "Track grain, hay, bedding, supplements and medical supplies. Set reorder thresholds for automatic low-stock alerts.",
    fields: [
      { key: "category", label: "Category", kind: "select",
        opts: ["grain", "hay", "bedding", "supplements", "medical", "blankets", "tack", "other"], required: true },
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
    desc: "Standing routines: turnout rotations, med rounds, blanketing, lesson blocks. These power the daily Today view.",
    fields: [
      { key: "type", label: "Type", kind: "select",
        opts: ["turnout", "feed", "medication", "blanketing", "lesson_block", "training_ride"], required: true },
      { key: "name", label: "Name", placeholder: "Morning turnout — Geldings A", required: true },
      { key: "time", label: "Time", placeholder: "07:30" },
      { key: "days_of_week", label: "Days (comma-sep)", placeholder: "mon, tue, wed, thu, fri", kind: "csv" },
      { key: "notes", label: "Notes" },
    ],
    display: (r) => `${r.type.replace("_", " ")} · ${r.name} · ${r.time || ""} · ${(r.days_of_week || []).join("/")}`,
  },
};

const CrudStep = ({ kind, onAnyChange }) => {
  const cfg = CRUD_CONFIG[kind];
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const load = () => api.get(cfg.endpoint).then((r) => setItems(r.data));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [kind]);

  const updateForm = (k, v) => { setForm({ ...form, [k]: v }); onAnyChange(); };

  const submit = async (e) => {
    e.preventDefault();
    const required = cfg.fields.filter((f) => f.required).map((f) => f.key);
    for (const k of required) {
      if (!form[k]) { toast.error(`${k} is required`); return; }
    }
    setSaving(true);
    try {
      const payload = { ...form };
      cfg.fields.forEach((f) => {
        if (f.kind === "csv" && typeof payload[f.key] === "string") {
          payload[f.key] = payload[f.key].split(",").map((s) => s.trim()).filter(Boolean);
        }
        if (f.type === "number" && payload[f.key] !== undefined && payload[f.key] !== "") {
          payload[f.key] = Number(payload[f.key]);
        }
      });
      await api.post(cfg.endpoint, payload);
      setForm({}); load();
      toast.success("Added");
    } catch {
      toast.error("Failed to add");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => { await api.delete(`${cfg.endpoint}/${id}`); load(); };

  return (
    <div data-testid={`step-${kind}`}>
      <p className="text-equine-silver/70 text-[14px] mb-5">{cfg.desc}</p>
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {cfg.fields.map((f) => f.kind === "select" ? (
          <Select
            key={f.key}
            label={f.label}
            value={form[f.key] || ""}
            onChange={(v) => updateForm(f.key, v)}
            options={f.opts.map((o) => ({ v: o, l: o.replace("_", " ") }))}
            testid={`${kind}-${f.key}`}
          />
        ) : (
          <Field
            key={f.key}
            label={f.label}
            type={f.type}
            value={form[f.key] || ""}
            onChange={(v) => updateForm(f.key, v)}
            placeholder={f.placeholder}
            testid={`${kind}-${f.key}`}
          />
        ))}
        <div className="md:col-span-2">
          <button disabled={saving} className="btn-primary inline-flex items-center gap-2" data-testid={`${kind}-add`}>
            <Plus className="w-4 h-4" /> {saving ? "Adding…" : "Add"}
          </button>
        </div>
      </form>

      <div className="label-eyebrow mb-2">Existing · {items.length}</div>
      <div className="space-y-2">
        {items.length === 0 && (
          <div className="text-equine-platinum/60 text-sm py-4">None yet — add your first above.</div>
        )}
        {items.map((it) => (
          <div key={it.id} className="flex items-center justify-between py-3 px-4 rounded-lg bg-equine-soft border border-equine-graphite/40">
            <div className="text-[13.5px] text-equine-silver capitalize">{cfg.display(it)}</div>
            <button
              onClick={() => remove(it.id)}
              data-testid={`${kind}-remove-${it.id}`}
              className="text-equine-platinum/60 hover:text-equine-clay p-1.5 rounded"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CrudStep;
