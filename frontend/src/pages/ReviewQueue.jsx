import React, { useEffect, useState, useCallback } from "react";
import { Navigate } from "react-router-dom";
import { api, fmtDate } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { PageHeader, Card, StatusPill } from "../components/Primitives";
import { Check, RotateCcw, Loader2, ShieldAlert, ClipboardCheck } from "lucide-react";
import { toast } from "sonner";

const REVIEW_ROLES = ["admin", "barn_manager", "trainer"];

/**
 * Phase 7C-3 — Manager Review Queue.
 *
 * Reviewers ({admin, barn_manager, trainer}) clear `pending_review` Owner Updates:
 * Approve (-> published) or Request changes (-> draft, optional note). Four-eyes is
 * enforced in the UI (and by the backend): a reviewer cannot approve a SENSITIVE
 * update they authored. After each action a `owner-updates-changed` window event
 * refreshes the sidebar pending badge instantly. No backend changes.
 */
export default function ReviewQueue() {
  const { user } = useAuth();
  const canReview = REVIEW_ROLES.includes(user?.role);

  const [items, setItems] = useState(null);
  const [horses, setHorses] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [noteFor, setNoteFor] = useState(null);
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    api
      .get("/owner-updates?status=pending_review")
      .then((r) => setItems(Array.isArray(r.data) ? r.data : []))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => {
    if (!canReview) return;
    load();
    api.get("/horses").then((r) => setHorses(r.data || [])).catch(() => {});
    const onChange = () => load();
    window.addEventListener("owner-updates-changed", onChange);
    return () => window.removeEventListener("owner-updates-changed", onChange);
  }, [canReview, load]);

  if (!canReview) return <Navigate to="/" replace />;

  const horseName = (id) => horses.find((h) => h.id === id)?.name || "Horse";
  const ping = () => window.dispatchEvent(new Event("owner-updates-changed"));

  const approve = async (u) => {
    setBusyId(u.id);
    try {
      await api.post(`/owner-updates/${u.id}/approve`);
      toast.success("Approved & published to the owner.");
      ping();
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not approve this update.");
    } finally {
      setBusyId(null);
    }
  };

  const submitNote = async () => {
    const id = noteFor;
    setBusyId(id);
    try {
      await api.post(`/owner-updates/${id}/request-changes`, { review_note: note.trim() || null });
      toast.success("Sent back to the author for changes.");
      setNoteFor(null);
      setNote("");
      ping();
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send this update back.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div data-testid="review-queue">
      <PageHeader
        eyebrow="Owner Trust"
        title="Review Queue"
        subtitle="Sensitive and submitted owner updates waiting for a reviewer."
      />

      {items === null && (
        <div className="py-12 text-center text-equine-platinum/50 text-[13px]">Loading the queue…</div>
      )}

      {items !== null && items.length === 0 && (
        <Card className="text-center py-12" data-testid="review-empty">
          <ClipboardCheck className="w-7 h-7 text-equine-champagne/70 mx-auto mb-3" strokeWidth={1.5} />
          <div className="text-[14px] text-equine-ivory">Nothing is waiting for review.</div>
          <div className="text-[12px] text-equine-platinum/50 mt-1">Submitted updates will appear here for approval.</div>
        </Card>
      )}

      {items !== null && items.length > 0 && (
        <div className="space-y-3">
          {items.map((u) => {
            const busy = busyId === u.id;
            const blocked = u.sensitive && u.author_user_id === user.id;
            return (
              <Card key={u.id} hover={false} data-testid={`review-row-${u.id}`}>
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <StatusPill tone="warning">awaiting review</StatusPill>
                  <span className="text-[12.5px] text-equine-ivory font-medium">{horseName(u.horse_id)}</span>
                  <span className="text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full bg-equine-soft border border-equine-steel/30 text-equine-platinum/70 capitalize">{u.kind}</span>
                  <span className="text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full bg-equine-soft border border-equine-steel/30 text-equine-platinum/70">{u.visibility.replace("_", " ")}</span>
                  {u.sensitive && <span className="text-[10px] uppercase tracking-[0.18em] text-equine-champagne/80">sensitive</span>}
                  <span className="ml-auto text-[11px] text-equine-platinum/40">{fmtDate(u.created_at)}</span>
                </div>

                <p className="text-[13.5px] text-equine-silver/85 leading-relaxed whitespace-pre-line mb-3">{u.body}</p>

                {blocked && (
                  <div className="flex items-center gap-2 mb-3 text-[12px] text-equine-champagne/90" data-testid={`review-approve-blocked-${u.id}`}>
                    <ShieldAlert className="w-3.5 h-3.5" /> You authored this — another reviewer must approve.
                  </div>
                )}

                <div className="flex gap-2 flex-wrap">
                  <button
                    data-testid={`review-approve-${u.id}`}
                    onClick={() => approve(u)}
                    disabled={busy || blocked}
                    className="inline-flex items-center gap-1.5 btn-primary !py-1.5 !px-3 text-[12.5px] disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Approve
                  </button>
                  <button
                    data-testid={`review-request-changes-${u.id}`}
                    onClick={() => { setNoteFor(u.id); setNote(""); }}
                    disabled={busy}
                    className="inline-flex items-center gap-1.5 !py-1.5 !px-3 text-[12.5px] rounded-lg border border-equine-steel/40 text-equine-platinum/80 hover:text-equine-ivory hover:border-equine-champagne transition-colors disabled:opacity-50"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Request changes
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Request-changes note modal (optional note) */}
      {noteFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4" data-testid="review-note-modal">
          <div className="w-full max-w-md bg-equine-navy border border-equine-steel/30 rounded-2xl p-6">
            <h3 className="font-display text-xl text-equine-ivory mb-1">Request changes</h3>
            <p className="text-[12.5px] text-equine-platinum/60 mb-4">Add an optional note for the author. The update returns to draft.</p>
            <textarea
              data-testid="review-note-input"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder="Optional: what should change before this is published?"
              className="w-full bg-equine-soft border border-equine-steel/40 rounded-lg px-3 py-2 text-[13px] text-equine-ivory placeholder:text-equine-platinum/40 focus:outline-none focus:border-equine-champagne"
            />
            <div className="flex gap-2 justify-end mt-4">
              <button onClick={() => { setNoteFor(null); setNote(""); }} className="text-[12.5px] text-equine-platinum/60 hover:text-equine-ivory px-3 py-2">Cancel</button>
              <button data-testid="review-note-submit" onClick={submitNote} disabled={busyId === noteFor} className="btn-primary !py-2 !px-4 text-[12.5px] disabled:opacity-50">Send back</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
