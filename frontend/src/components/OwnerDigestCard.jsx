import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./Primitives";
import { Mail, Send, Loader2, Calendar } from "lucide-react";
import { toast } from "sonner";

/**
 * Lightweight, owner-facing card that previews tomorrow morning's digest
 * and (optionally) this week's Sunday recap. Calm, composed — no analytics.
 * One toggle governs both surfaces (digest_enabled).
 */
export default function OwnerDigestCard() {
  const [preview, setPreview] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [tab, setTab] = useState("daily");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [savingPref, setSavingPref] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [prevR, weeklyR, prefR] = await Promise.all([
        api.post("/notifications/digest/preview"),
        api.post("/notifications/weekly-recap/preview"),
        api.get("/notifications/preferences"),
      ]);
      setPreview(prevR.data);
      setWeekly(weeklyR.data);
      setEnabled(prefR.data?.digest_enabled !== false);
    } catch {
      // silent — keep card calm
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const active = tab === "daily" ? preview : weekly;
  const sendEndpoint = tab === "daily"
    ? "/notifications/digest/send-me"
    : "/notifications/weekly-recap/send-me";

  const sendNow = async () => {
    setSending(true);
    try {
      const r = await api.post(sendEndpoint);
      if (r.data?.sent) {
        toast.success(tab === "daily"
          ? "Today's digest is on its way."
          : "This week's recap is on its way.");
      } else if (r.data?.reason === "no_updates") {
        toast.message("Nothing new to share yet.");
      } else {
        toast.message("Queued.");
      }
    } catch {
      toast.error("Could not send.");
    } finally {
      setSending(false);
    }
  };

  const toggleEnabled = async (v) => {
    setEnabled(v);
    setSavingPref(true);
    try {
      await api.put("/notifications/preferences", { digest_enabled: v });
      toast.success(v
        ? "Daily digest & weekly recap enabled."
        : "Digest & recap paused.");
      if (v) load();
    } catch {
      setEnabled(!v);
      toast.error("Could not update preference.");
    } finally {
      setSavingPref(false);
    }
  };

  return (
    <Card className="mb-8" data-testid="owner-digest-card">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
            <Mail strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
          </div>
          <div>
            <h2 className="font-display text-2xl text-equine-ink">Owner updates</h2>
            <div className="text-[12.5px] text-equine-inkMuted">
              A short morning digest plus a calm Sunday recap. Only what matters for your horse.
            </div>
          </div>
        </div>
        <label className="flex items-center gap-2 text-[12.5px] text-equine-inkMuted cursor-pointer select-none">
          <span>{enabled ? "On" : "Paused"}</span>
          <button
            data-testid="digest-enabled-toggle"
            type="button"
            onClick={() => toggleEnabled(!enabled)}
            disabled={savingPref}
            aria-pressed={enabled}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
              enabled ? "bg-equine-navy" : "bg-equine-graphite/40"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform ${
                enabled ? "translate-x-5" : "translate-x-1"
              }`}
            />
          </button>
        </label>
      </div>

      <div className="flex items-center gap-1.5 mb-3" data-testid="digest-tabs" role="tablist">
        {[
          { id: "daily", label: "Morning digest", icon: Mail },
          { id: "weekly", label: "Sunday recap", icon: Calendar },
        ].map((t) => {
          const Icon = t.icon;
          const isActive = tab === t.id;
          return (
            <button
              key={t.id}
              data-testid={`digest-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              role="tab"
              aria-selected={isActive}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] tracking-wide border transition-colors ${
                isActive
                  ? "bg-equine-navy text-white border-equine-navy"
                  : "bg-equine-card text-equine-inkMuted border-equine-hairline hover:border-equine-graphite"
              }`}
            >
              <Icon className="w-3 h-3" /> {t.label}
            </button>
          );
        })}
      </div>

      <div className="bg-equine-soft/60 border border-equine-hairline rounded-xl px-5 py-4" data-testid="digest-preview-body">
        {loading ? (
          <div className="text-[13px] text-equine-inkSoft inline-flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Composing preview…
          </div>
        ) : !active || active.empty ? (
          <div className="text-[13px] text-equine-inkSoft">
            {tab === "daily"
              ? "All quiet today — nothing meaningful to share yet. We'll write again when there's real news."
              : "A quiet week — no recap needed. We'll be back when there's something to share."}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="uppercase tracking-[0.22em] text-[10.5px] text-equine-inkSoft">
              Preview · {active.payload?.updates_count} update{active.payload?.updates_count === 1 ? "" : "s"}
            </div>
            {(active.payload?.sections || []).map((sec) => (
              <div key={sec.horse_id} className="border-t border-equine-hairline pt-2.5 first:border-0 first:pt-0">
                <div className="text-[11px] uppercase tracking-[0.18em] text-equine-inkSoft mb-1">
                  {sec.horse_name}
                </div>
                {sec.lines.map((ln, i) => (
                  <p key={i} className="text-[14px] text-equine-ink leading-snug">{ln}</p>
                ))}
              </div>
            ))}
            {tab === "weekly" && active.payload?.upcoming_count > 0 && (
              <div className="border-t border-equine-hairline pt-2.5">
                <div className="text-[11px] uppercase tracking-[0.18em] text-equine-inkSoft mb-1">
                  Looking ahead
                </div>
                <p className="text-[14px] text-equine-ink leading-snug">
                  {active.payload.upcoming_count} upcoming care appointment{active.payload.upcoming_count === 1 ? "" : "s"} scheduled in the next 7 days.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-end gap-3">
        <button
          data-testid="digest-send-me-btn"
          onClick={sendNow}
          disabled={sending || !enabled || loading || active?.empty}
          className="btn-secondary inline-flex items-center gap-2 disabled:opacity-50"
        >
          {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          {sending ? "Sending…" : "Send to me now"}
        </button>
      </div>
    </Card>
  );
}
