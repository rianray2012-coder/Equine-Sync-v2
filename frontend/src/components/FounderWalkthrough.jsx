/**
 * Founder Walkthrough — a calm, narrated, READ-ONLY tour of one barn-day.
 *
 * Two minutes maximum. No real mutations. No flashy animation.
 * It should feel like a thoughtful barn manager talking the founder
 * through their app — not a sales demo.
 *
 * Architectural notes:
 *   • Pure overlay component — no router changes, no global state.
 *   • Visible only when explicitly opened (FounderWalkthroughButton).
 *   • Closes on Escape / backdrop click / final-step "I've got it" button.
 *   • Persists the "I've seen it" flag in localStorage so a returning
 *     founder isn't auto-prompted, but the button stays available.
 *   • All API reads are GETs the user already has access to — no demo
 *     seeding, no synthetic state, no operational side-effects.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import {
  Sunrise, UtensilsCrossed, Pill, Mail, X, ChevronRight,
  ChevronLeft, Heart, Sparkles,
} from "lucide-react";

const STORAGE_KEY = "equinesync.walkthrough.seen";

const STEPS = [
  {
    id: "today",
    icon: Sunrise,
    eyebrow: "Step 1 of 6 · Morning",
    title: "Open Today",
    body: "The day always begins here. Today consolidates feeding, medications, turnout, rehab and lessons into one urgency-ordered stream — overdue first, due-now next, then a calm look ahead.",
    cta: { to: "/today", label: "Glance at Today" },
    fetch: async () => {
      const r = await api.get("/tasks/today");
      const groups = r.data?.groups || {};
      return {
        right_now: (groups.overdue_critical?.length || 0) + (groups.due_now?.length || 0),
        next_4h: groups.upcoming_next_4h?.length || 0,
        later: groups.later_today?.length || 0,
      };
    },
    renderStat: (d) => d && (
      <>
        <Stat label="Right now"  value={d.right_now} accent="amber" />
        <Stat label="Next 4 hours" value={d.next_4h}  accent="brass" />
        <Stat label="Later today" value={d.later}   accent="neutral" />
      </>
    ),
  },
  {
    id: "feed",
    icon: UtensilsCrossed,
    eyebrow: "Step 2 of 6 · Morning",
    title: "Complete one feed task",
    body: "Each task taps once to mark done — on mobile you can swipe right instead. Every completion writes through the unified Task Engine, so feed adherence, owner timelines and the morning digest all stay in sync automatically.",
    cta: { to: "/feed", label: "See feed tasks" },
    fetch: async () => {
      const r = await api.get("/tasks/today");
      const feed = (Object.values(r.data?.groups || {}).flat()).filter((t) => t.category === "feed");
      return {
        total: feed.length,
        done: feed.filter((t) => t.status === "completed").length,
      };
    },
    renderStat: (d) => d && (
      <>
        <Stat label="Feed today" value={d.total} accent="brass" />
        <Stat label="Logged"     value={d.done}  accent="sage" />
      </>
    ),
  },
  {
    id: "meds",
    icon: Pill,
    eyebrow: "Step 3 of 6 · Late morning",
    title: "Log one medication",
    body: "Medication completions carry an outcome — given, refused, skipped — and a one-line note if needed. Refusals automatically appear in the vet timeline and shape the owner's morning digest tone.",
    cta: { to: "/medications", label: "See medications" },
    fetch: async () => {
      const r = await api.get("/dashboard/summary");
      return { due: r.data?.meds_due || 0, missed: r.data?.meds_missed || 0 };
    },
    renderStat: (d) => d && (
      <>
        <Stat label="Due"    value={d.due}    accent="amber" />
        <Stat label="Missed" value={d.missed} accent={d.missed > 0 ? "clay" : "sage"} />
      </>
    ),
  },
  {
    id: "timeline",
    icon: Heart,
    eyebrow: "Step 4 of 6 · Afternoon",
    title: "Review the horse timeline",
    body: "Each horse has a curated care timeline — vet visits, farrier days, rehab progress, medication adherence. Owners see a calmer, owner-visible slice of the same data, never the operational backstage.",
    cta: { to: "/horses", label: "See horses" },
    fetch: async () => {
      const r = await api.get("/horses");
      const horses = r.data || [];
      const stallRest = horses.filter((h) => h.status === "stall_rest" || h.status === "rehab").length;
      return { total: horses.length, stallRest };
    },
    renderStat: (d) => d && (
      <>
        <Stat label="Horses"     value={d.total}     accent="brass" />
        <Stat label="Stall rest" value={d.stallRest} accent={d.stallRest > 0 ? "amber" : "sage"} />
      </>
    ),
  },
  {
    id: "digest",
    icon: Mail,
    eyebrow: "Step 5 of 6 · Evening",
    title: "Preview the owner digest",
    body: "Owners receive a calm morning email plus a quiet Sunday recap. No analytics noise — just the meaningful care moments. Composed automatically from the day's task events; nothing for the barn to write.",
    cta: { to: "/owner-portal", label: "See Owner Portal" },
    fetch: async () => null,
    renderStat: () => (
      <div className="text-[12.5px] text-equine-platinum/65 leading-relaxed col-span-full">
        Each owner can preview their own digest from the Owner Portal. As a barn manager,
        you can trigger a same-day digest pass from <span className="text-equine-ivory">Settings → Notifications</span>.
      </div>
    ),
  },
  {
    id: "ready",
    icon: Sparkles,
    eyebrow: "Step 6 of 6 · You're ready",
    title: "That's the rhythm of one barn day.",
    body: "Everything you saw runs through one engine, one set of events, one timeline. Add a horse, invite a groom, send the first feed completion — operations begin the moment you do. Nothing here is locked or required to start.",
    cta: { to: "/today", label: "Begin today" },
    fetch: async () => null,
    renderStat: () => (
      <div className="text-[12.5px] text-equine-platinum/65 leading-relaxed col-span-full italic">
        We&apos;ll stay quiet from here. The Today view will be your home.
      </div>
    ),
  },
];

const Stat = ({ label, value, accent }) => {
  const tone = {
    sage:    "text-equine-sage",
    brass:   "text-equine-brassLight",
    amber:   "text-equine-amber",
    clay:    "text-equine-clay",
    neutral: "text-equine-ivory",
  }[accent] || "text-equine-ivory";
  return (
    <div className="rounded-xl bg-equine-soft border border-equine-graphite/40 px-4 py-3">
      <div className="label-eyebrow">{label}</div>
      <div className={`font-display text-3xl mt-0.5 ${tone}`}>{value ?? "—"}</div>
    </div>
  );
};

export default function FounderWalkthrough({ open, onClose }) {
  const [idx, setIdx] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  // Reset to step 0 each time the modal is reopened.
  useEffect(() => { if (open) setIdx(0); }, [open]);

  // Lazy-load the per-step stat each time the index changes.
  useEffect(() => {
    if (!open) return;
    const step = STEPS[idx];
    if (!step?.fetch) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    setData(null);
    step.fetch()
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [idx, open]);

  // Escape to close.
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  const step = STEPS[idx];
  const Icon = step.icon;
  const isLast = idx === STEPS.length - 1;

  const finish = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch {}
    onClose();
  };

  return (
    <div
      data-testid="founder-walkthrough"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-equine-navyDeep/55 backdrop-blur-md px-3 pt-4 pb-4 sm:p-6"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-equine-card border border-equine-hairline rounded-3xl shadow-2xl w-full max-w-xl p-6 sm:p-8 animate-fade-in">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-2xl bg-equine-steel/25 border border-equine-steel/40 flex items-center justify-center flex-shrink-0">
              <Icon strokeWidth={1.4} className="text-equine-champagne w-5 h-5" />
            </div>
            <div>
              <div className="label-eyebrow">{step.eyebrow}</div>
              <h3 className="font-display text-2xl text-equine-ivory mt-0.5 leading-tight">
                {step.title}
              </h3>
            </div>
          </div>
          <button
            onClick={onClose}
            data-testid="walkthrough-close"
            className="text-equine-platinum/60 hover:text-equine-ivory p-1.5 -m-1.5"
            aria-label="Close walkthrough"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-[14px] text-equine-silver/85 leading-relaxed mb-5">
          {step.body}
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 mb-5 min-h-[64px]">
          {loading
            ? <div className="text-[12.5px] text-equine-platinum/50 col-span-full">Loading…</div>
            : step.renderStat(data)}
        </div>

        {step.cta && (
          <Link
            to={step.cta.to}
            onClick={onClose}
            data-testid={`walkthrough-cta-${step.id}`}
            className="inline-flex items-center gap-1.5 text-[12.5px] text-equine-champagne hover:text-equine-brassLight transition-colors mb-5"
          >
            {step.cta.label} <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        )}

        {/* Progress dots */}
        <div className="flex items-center justify-center gap-1.5 mb-5">
          {STEPS.map((s, i) => (
            <span
              key={s.id}
              data-testid={`walkthrough-dot-${i}`}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === idx ? "w-6 bg-equine-champagne" : "w-1.5 bg-equine-graphite/50"
              }`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            disabled={idx === 0}
            data-testid="walkthrough-prev"
            className="btn-secondary disabled:opacity-40 inline-flex items-center gap-1.5 !py-2 !px-3"
          >
            <ChevronLeft className="w-4 h-4" /> Back
          </button>
          {isLast ? (
            <button
              onClick={finish}
              data-testid="walkthrough-finish"
              className="btn-primary inline-flex items-center gap-2 !py-2 !px-4"
            >
              I&apos;ve got it
            </button>
          ) : (
            <button
              onClick={() => setIdx((i) => Math.min(STEPS.length - 1, i + 1))}
              data-testid="walkthrough-next"
              className="btn-primary inline-flex items-center gap-1.5 !py-2 !px-4"
            >
              Continue <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Convenience hook: has the founder already seen the walkthrough? */
export const walkthroughSeen = () => {
  try { return localStorage.getItem(STORAGE_KEY) === "1"; }
  catch { return false; }
};
