import React, { useState, useEffect } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { Field, Select } from "./onboarding/FormPrimitives";

/**
 * QuickAddSheet — a calm right-side modal sheet for "Add X" flows.
 *
 * Built on a plain backdrop + slide-in card (avoiding Radix Dialog so it
 * coexists cleanly with the existing sonner toaster / shadcn primitives).
 * Reuses Field + Select from onboarding so the form aesthetic matches
 * the Setup Concierge exactly — operationally familiar, no new visual
 * vocabulary.
 *
 * Props:
 *   open           — boolean controlling visibility
 *   onClose()      — close handler
 *   title          — sheet title (e.g. "Add Owner")
 *   eyebrow        — small label above title
 *   fields         — [{ key, label, type?, kind?, opts?, required?, placeholder?, full? }]
 *                    `full: true` makes the field span both columns
 *                    `kind: "textarea"` renders a multi-line input
 *                    `kind: "select"` renders the shadcn select
 *   endpoint       — POST endpoint relative to /api (e.g. "/owners")
 *   transform?     — optional (form) => payload remap before POST
 *   onCreated(doc) — called after successful POST with response.data
 *   submitLabel?   — defaults to "Add"
 *   testidPrefix?  — defaults derived from endpoint; e.g. "owner-add"
 */
export default function QuickAddSheet({
  open,
  onClose,
  title,
  eyebrow,
  fields,
  endpoint,
  transform,
  onCreated,
  submitLabel = "Add",
  testidPrefix,
}) {
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  // Reset on each open so leftover state doesn't bleed between adds.
  useEffect(() => { if (open) setForm({}); }, [open]);

  const prefix = testidPrefix || `${endpoint.replace(/^\//, "").replace(/[^a-z]+/gi, "-")}-add`;

  const submit = async (e) => {
    e?.preventDefault();
    for (const f of fields) {
      if (f.required && (form[f.key] === undefined || form[f.key] === "")) {
        toast.error(`${f.label} is required`);
        return;
      }
    }
    setSaving(true);
    try {
      let payload = { ...form };
      fields.forEach((f) => {
        if (f.type === "number" && payload[f.key] !== undefined && payload[f.key] !== "") {
          payload[f.key] = Number(payload[f.key]);
        }
      });
      if (typeof transform === "function") payload = transform(payload);
      const r = await api.post(endpoint, payload);
      toast.success("Added");
      onCreated?.(r.data);
      onClose?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex justify-end"
      data-testid={`${prefix}-sheet`}
      onKeyDown={(e) => { if (e.key === "Escape") onClose?.(); }}
    >
      <div
        className="absolute inset-0 bg-equine-black/70 backdrop-blur-sm animate-in fade-in-0 duration-200"
        onClick={onClose}
      />
      <div className="relative h-full w-full max-w-md bg-equine-navy border-l border-white/10 shadow-2xl overflow-y-auto scrollbar-luxe animate-in slide-in-from-right-4 duration-300">
        <div className="sticky top-0 z-10 bg-equine-navy/95 backdrop-blur-md border-b border-white/[0.06] px-6 py-5 flex items-start justify-between gap-3">
          <div>
            {eyebrow && <div className="label-eyebrow mb-1">{eyebrow}</div>}
            <h2 className="font-display text-2xl text-equine-ivory">{title}</h2>
          </div>
          <button
            onClick={onClose}
            data-testid={`${prefix}-close`}
            className="text-equine-platinum/60 hover:text-equine-ivory p-1.5 rounded-md hover:bg-white/[0.05] transition-colors"
            aria-label="Close"
          >
            <X strokeWidth={1.6} className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={submit} className="px-6 py-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {fields.map((f) => {
              const wrapperCls = f.full ? "sm:col-span-2" : "";
              if (f.kind === "select") {
                // Radix Select disallows value="" — silently strip empty options so
                // future callers can't crash the modal by trying to add a
                // "— None —" placeholder row. Use a non-empty sentinel
                // (e.g. "__none__") and coerce it in your transform() instead.
                const opts = f.opts
                  .map((o) => (typeof o === "string" ? { v: o, l: o.replace(/_/g, " ") } : o))
                  .filter((o) => o.v !== "" && o.v !== undefined && o.v !== null);
                return (
                  <div key={f.key} className={wrapperCls}>
                    <Select
                      label={f.label}
                      value={form[f.key] || ""}
                      onChange={(v) => setForm((s) => ({ ...s, [f.key]: v }))}
                      options={opts}
                      testid={`${prefix}-${f.key}`}
                    />
                  </div>
                );
              }
              if (f.kind === "textarea") {
                return (
                  <label key={f.key} className={`block ${wrapperCls}`}>
                    <div className="label-eyebrow mb-1.5">{f.label}</div>
                    <textarea
                      rows={f.rows || 3}
                      value={form[f.key] || ""}
                      placeholder={f.placeholder}
                      onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
                      data-testid={`${prefix}-${f.key}`}
                      className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory focus:border-equine-champagne outline-none text-[14px] transition-colors resize-y"
                    />
                  </label>
                );
              }
              return (
                <div key={f.key} className={wrapperCls}>
                  <Field
                    label={f.label}
                    type={f.type}
                    placeholder={f.placeholder}
                    value={form[f.key] || ""}
                    onChange={(v) => setForm((s) => ({ ...s, [f.key]: v }))}
                    testid={`${prefix}-${f.key}`}
                  />
                </div>
              );
            })}
          </div>

          <div className="pt-3 flex items-center justify-end gap-2 hairline mt-4">
            <button
              type="button"
              onClick={onClose}
              data-testid={`${prefix}-cancel`}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              data-testid={`${prefix}-submit`}
              className="btn-primary"
            >
              {saving ? "Saving…" : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
