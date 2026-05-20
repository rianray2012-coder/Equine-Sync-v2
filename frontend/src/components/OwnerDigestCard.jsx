import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./Primitives";
import { Mail, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

/**
 * Lightweight, owner-facing card that previews tomorrow morning's digest
 * and lets the owner opt in/out or trigger a copy now. Designed to feel
 * calm and composed — no analytics, no charts, no operational noise.
 */
export default function OwnerDigestCard() {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [savingPref, setSavingPref] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [prevR, prefR] = await Promise.all([
        api.post("/notifications/digest/preview"),
        api.get("/notifications/preferences"),
      ]);
      setPreview(prevR.data);
      setEnabled(prefR.data?.digest_enabled !== false);
    } catch {
      // silent — keep card calm
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const sendNow = async () => {
    setSending(true);
    try {
      const r = await api.post("/notifications/digest/send-me");
      if (r.data?.sent) toast.success("Today's digest is on its way.");
      else if (r.data?.reason === "no_updates") toast.message("Nothing new to share today.");
      else toast.message("Digest queued.");
    } catch {
      toast.error("Could not send digest.");
    } finally {
      setSending(false);
    }
  };

  const toggleEnabled = async (v) => {
    setEnabled(v);
    setSavingPref(true);
    try {
      await api.put("/notifications/preferences", { digest_enabled: v });
      toast.success(v ? "Daily digest enabled." : "Daily digest paused.");
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
            <h2 className="font-display text-2xl text-equine-ink">Morning digest</h2>
            <div className="text-[12.5px] text-equine-inkMuted">
              A short, calm note from the barn each morning — only what matters for your horse.
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

      <div className="bg-equine-soft/60 border border-equine-hairline rounded-xl px-5 py-4" data-testid="digest-preview-body">
        {loading ? (
          <div className="text-[13px] text-equine-inkSoft inline-flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Composing today's preview…
          </div>
        ) : !preview || preview.empty ? (
          <div className="text-[13px] text-equine-inkSoft">
            All quiet today — nothing meaningful to share yet. We&apos;ll write again when there&apos;s real news.
          </div>
        ) : (
          <div className="space-y-3">
            <div className="uppercase tracking-[0.22em] text-[10.5px] text-equine-inkSoft">
              Preview · {preview.payload?.updates_count} update{preview.payload?.updates_count === 1 ? "" : "s"}
            </div>
            {(preview.payload?.sections || []).map((sec) => (
              <div key={sec.horse_id} className="border-t border-equine-hairline pt-2.5 first:border-0 first:pt-0">
                <div className="text-[11px] uppercase tracking-[0.18em] text-equine-inkSoft mb-1">
                  {sec.horse_name}
                </div>
                {sec.lines.map((ln, i) => (
                  <p key={i} className="text-[14px] text-equine-ink leading-snug">{ln}</p>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-end gap-3">
        <button
          data-testid="digest-send-me-btn"
          onClick={sendNow}
          disabled={sending || !enabled || loading || preview?.empty}
          className="btn-secondary inline-flex items-center gap-2 disabled:opacity-50"
        >
          {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          {sending ? "Sending…" : "Send to me now"}
        </button>
      </div>
    </Card>
  );
}
