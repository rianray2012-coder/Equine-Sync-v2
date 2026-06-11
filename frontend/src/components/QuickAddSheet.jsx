import React, { useState, useEffect, useRef, useCallback } from "react";
import { X, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { Select } from "./onboarding/FormPrimitives";

const DRAFT_KEY = (endpoint) => `equine_draft_${endpoint}`;

/**
 * Shallow-equal for primitive object comparisons — used to gate the
 * "reset form to initial" effect so that parent re-renders that produce
 * a new object literal but the same VALUES don't blow away in-progress edits.
 */
const shallowEqual = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const ak = Object.keys(a), bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  for (const k of ak) if (a[k] !== b[k]) return false;
  return true;
};

/**
 * QuickAddSheet — calm right-side modal for "Add X" flows.
 *
 * Batch-A hardening (Feb 20 2026 — operational hardening sprint):
 *   • Auto-focus first interactive field on open
 *   • Press Enter to submit (native form behaviour; textareas excluded)
 *   • initialValues prop for smart defaults (now / today / next half-hour)
 *   • Draft preservation via sessionStorage keyed by endpoint:
 *       - debounced save on form change
 *       - silent restore on reopen (no banner; matches founder direction)
 *       - cleared after a successful POST
 *
 * Batch-B hardening:
 *   • On POST failure → sheet STAYS open with inline calm message
 *     ("Saved as draft — try again when you have signal") + form intact
 *     so the user never loses the work mid-aisle.
 *
 * Props:
 *   open / onClose / title / eyebrow
 *   fields          [{ key, label, type?, kind?, opts?, required?, placeholder?, full?, rows? }]
 *   endpoint        POST endpoint (e.g. "/owners")
 *   initialValues?  object merged BEFORE any restored draft. Use for smart defaults.
 *   transform?      (form) => payload remap before POST
 *   onCreated(doc)  called after successful POST
 *   submitLabel?    default "Add"
 *   testidPrefix?   default derived from endpoint
 */
export default function QuickAddSheet({
  open,
  onClose,
  title,
  eyebrow,
  fields,
  endpoint,
  initialValues,
  transform,
  onCreated,
  renderWarnings,
  submitLabel = "Add",
  testidPrefix,
}) {
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  // We don't attach a ref directly to one field — Radix Select wraps inside
  // a div that isn't focusable. Instead we ref the whole form and query
  // for the first focusable element on open. This works for input,
  // textarea, and the Radix Select trigger button (role="combobox").
  const formRef = useRef(null);
  // Track the last "applied" initialValues by VALUE not by reference so
  // a parent that re-allocates the object literal every render doesn't
  // wipe in-progress user input.
  const appliedInitialRef = useRef(null);
  // Timestamp of last open — used to guard against Radix Select firing
  // onValueChange("") on its own mount, which would otherwise wipe the
  // smart-default we just set.
  const openedAtRef = useRef(0);
  const draftKey = DRAFT_KEY(endpoint);

  // Reset + smart-default + draft-restore on open (or when initial values change in *value*).
  useEffect(() => {
    if (!open) {
      appliedInitialRef.current = null;
      return undefined;
    }
    // Skip if these initialValues (by value) were already applied during this open cycle.
    if (shallowEqual(appliedInitialRef.current, initialValues)) return undefined;
    appliedInitialRef.current = initialValues || {};
    openedAtRef.current = Date.now();

    let initial = { ...(initialValues || {}) };
    try {
      const stored = sessionStorage.getItem(draftKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Restore only if the draft has user content beyond defaults.
        const hasUserContent = Object.entries(parsed).some(
          ([k, v]) => v !== undefined && v !== "" && v !== (initialValues || {})[k],
        );
        if (hasUserContent) initial = { ...initial, ...parsed };
      }
    } catch {
      /* ignore corrupted drafts silently */
    }
    setForm(initial);
    setError(null);

    // Defer focus so the slide-in animation completes first.
    const t = setTimeout(() => {
      const el = formRef.current?.querySelector(
        'input:not([type="hidden"]), textarea, button[role="combobox"]',
      );
      el?.focus?.();
    }, 320);
    return () => clearTimeout(t);
  }, [open, draftKey, initialValues]);

  // Debounced draft persistence (only while sheet is open and form changes).
  useEffect(() => {
    if (!open) return undefined;
    const handle = setTimeout(() => {
      try {
        // Don't persist a draft that's identical to initialValues — keeps storage clean.
        const isJustDefaults = Object.entries(form).every(
          ([k, v]) => v === (initialValues || {})[k],
        );
        if (isJustDefaults || Object.keys(form).length === 0) {
          sessionStorage.removeItem(draftKey);
        } else {
          sessionStorage.setItem(draftKey, JSON.stringify(form));
        }
      } catch {
        /* sessionStorage quota / disabled — fail silently */
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [form, open, draftKey, initialValues]);

  const prefix = testidPrefix || `${endpoint.replace(/^\//, "").replace(/[^a-z]+/gi, "-")}-add`;

  const update = useCallback((key, val) => {
    // Defensive guard: Radix Select can fire onValueChange("") during its
    // own mount even when given a non-empty controlled value. Within the
    // first 600ms of opening, ignore empty-string updates that would
    // clobber a smart-default we deliberately set.
    if (
      val === ""
      && Date.now() - openedAtRef.current < 600
      && appliedInitialRef.current
      && appliedInitialRef.current[key] !== undefined
      && appliedInitialRef.current[key] !== ""
    ) {
      return;
    }
    setForm((s) => ({ ...s, [key]: val }));
    if (error) setError(null);
  }, [error]);

  const submit = async (e) => {
    e?.preventDefault();
    for (const f of fields) {
      if (f.required && (form[f.key] === undefined || form[f.key] === "")) {
        toast.error(`${f.label} is required`);
        return;
      }
    }
    setSaving(true);
    setError(null);
    try {
      let payload = { ...form };
      fields.forEach((f) => {
        if (f.type === "number" && payload[f.key] !== undefined && payload[f.key] !== "") {
          payload[f.key] = Number(payload[f.key]);
        }
      });
      if (typeof transform === "function") payload = transform(payload);
      const r = await api.post(endpoint, payload);
      // Successful submit → clear draft + dismiss.
      try { sessionStorage.removeItem(draftKey); } catch { /* ignore */ }
      toast.success("Added");
      onCreated?.(r.data);
      onClose?.();
    } catch (err) {
      // Calm, non-blame language. Form data + draft remain intact.
      setError(
        err?.response?.data?.detail
        || "Saved as draft — try again when you have signal.",
      );
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
      <div className="relative h-full w-full max-w-md bg-equine-card border-l border-equine-hairline shadow-2xl overflow-y-auto scrollbar-luxe animate-in slide-in-from-right-4 duration-300">
        <div className="sticky top-0 z-10 bg-equine-card/95 backdrop-blur-md border-b border-equine-hairline px-6 py-5 flex items-start justify-between gap-3">
          <div>
            {eyebrow && <div className="label-eyebrow mb-1">{eyebrow}</div>}
            <h2 className="font-display text-2xl text-equine-ivory">{title}</h2>
          </div>
          <button
            onClick={onClose}
            data-testid={`${prefix}-close`}
            className="text-equine-platinum/60 hover:text-equine-ivory p-1.5 rounded-md hover:bg-white/[0.05] transition-colors tap-44"
            aria-label="Close"
          >
            <X strokeWidth={1.6} className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={submit} ref={formRef} className="px-6 py-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {fields.map((f) => {
              const wrapperCls = f.full ? "sm:col-span-2" : "";
              if (f.kind === "select") {
                const opts = f.opts
                  .map((o) => (typeof o === "string" ? { v: o, l: o.replace(/_/g, " ") } : o))
                  .filter((o) => o.v !== "" && o.v !== undefined && o.v !== null);
                return (
                  <div key={f.key} className={wrapperCls}>
                    <Select
                      label={f.label}
                      value={form[f.key] || ""}
                      onChange={(v) => update(f.key, v)}
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
                      onChange={(e) => update(f.key, e.target.value)}
                      data-testid={`${prefix}-${f.key}`}
                      className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory focus:border-equine-champagne outline-none text-[14px] transition-colors resize-y"
                    />
                  </label>
                );
              }
              return (
                <div key={f.key} className={wrapperCls}>
                  <label className="block">
                    <div className="label-eyebrow mb-1.5">{f.label}</div>
                    <input
                      type={f.type || "text"}
                      value={form[f.key] || ""}
                      onChange={(e) => update(f.key, e.target.value)}
                      placeholder={f.placeholder}
                      data-testid={`${prefix}-${f.key}`}
                      className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory focus:border-equine-champagne outline-none text-[14px] transition-colors min-h-[44px]"
                    />
                  </label>
                </div>
              );
            })}
          </div>

          {error && (
            <div
              data-testid={`${prefix}-error`}
              className="flex items-start gap-2.5 px-3.5 py-2.5 rounded-lg bg-equine-amber/8 border border-equine-amber/25 text-equine-amber text-[12.5px] leading-relaxed"
            >
              <AlertCircle strokeWidth={1.6} className="w-4 h-4 mt-px shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Soft, informational notes computed from the current form
              state. Used for scheduling-conflict awareness — never
              blocking, always supportive in tone. */}
          {typeof renderWarnings === "function" && renderWarnings(form, {
            prefix,
          })}

          <div className="sticky bottom-0 -mx-6 px-6 pt-3 pb-1 mt-4 bg-equine-card/95 backdrop-blur-md border-t border-equine-hairline flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              data-testid={`${prefix}-cancel`}
              className="btn-secondary tap-44"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              data-testid={`${prefix}-submit`}
              className="btn-primary tap-44"
            >
              {saving ? "Saving…" : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Tiny utility callers can import for "clear my draft" affordances (rarely needed).
export const clearDraft = (endpoint) => {
  try { sessionStorage.removeItem(DRAFT_KEY(endpoint)); } catch { /* ignore */ }
};
