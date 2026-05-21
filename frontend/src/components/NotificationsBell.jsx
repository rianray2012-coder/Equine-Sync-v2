import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, fmtTime, fmtDate } from "../lib/api";
import { Bell, CheckCheck, Inbox, Check, X, MessageSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";

const DECIDER_ROLES = ["admin", "barn_manager", "trainer"];

const REQUEST_TYPE_LABEL = {
  extra_ride: "Extra ride",
  trim_request: "Trim request",
  blanket_change: "Blanket change",
  body_clip: "Body clip",
  vet_appt: "Vet appointment",
  farrier_appt: "Farrier appointment",
  hand_walk: "Hand walk",
  schedule_change: "Schedule change",
  other: "Other request",
};

/**
 * NotificationsBell — quiet operational awareness, not a command center.
 *
 * Drawer composition:
 *   1. (Admin/Manager/Trainer only) Pending service requests — one-tap
 *      Approve + inline "Decline with a note" expansion. Saves owners
 *      4-12 hours of admin latency by removing the navigate-to-portal hop
 *      surfaced in OPERATIONAL_SIMULATION §5.3.
 *   2. Inbox — task-event notifications (existing behaviour, untouched).
 *
 * Tone constraints (Batch C, per founder direction):
 *   - Approve / Decline label only; no aggressive "Reject" wording.
 *   - Decline expands inline; no separate modal.
 *   - Decline reason is optional; submitting without a note still works.
 *   - Success toast: "Approved." or "Declined with a note." — never punitive.
 */
export default function NotificationsBell() {
  const { user } = useAuth();
  const canDecide = DECIDER_ROLES.includes(user?.role);

  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], unread: 0 });
  const [pending, setPending] = useState([]);
  // declineFor: id of the request whose inline reason composer is expanded.
  const [declineFor, setDeclineFor] = useState(null);
  const [declineReason, setDeclineReason] = useState("");
  const [busyId, setBusyId] = useState(null);
  const ref = useRef(null);

  const refresh = useCallback(() => {
    api.get("/notifications?limit=25")
      .then((r) => setData(r.data))
      .catch(() => {});
    if (canDecide) {
      api.get("/service-requests")
        .then((r) => setPending(
          (r.data || []).filter((s) => s.status === "pending"),
        ))
        .catch(() => {});
    } else {
      setPending([]);
    }
  }, [canDecide]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return undefined;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setDeclineFor(null);
        setDeclineReason("");
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const markAll = async () => {
    try {
      await api.post("/notifications/read-all");
      refresh();
    } catch (err) {
      console.warn("[notifications] mark-all failed", err);
    }
  };

  const markOne = async (id) => {
    try {
      await api.post(`/notifications/${id}/read`);
      refresh();
    } catch (err) {
      console.warn("[notifications] mark-one failed", err);
    }
  };

  const approve = async (id) => {
    setBusyId(id);
    try {
      await api.post(`/service-requests/${id}/approve`);
      toast.success("Approved.");
      refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not approve.");
    } finally {
      setBusyId(null);
    }
  };

  const openDecline = (id) => {
    setDeclineFor(id);
    setDeclineReason("");
  };

  const cancelDecline = () => {
    setDeclineFor(null);
    setDeclineReason("");
  };

  const submitDecline = async () => {
    if (!declineFor) return;
    setBusyId(declineFor);
    try {
      await api.post(`/service-requests/${declineFor}/decline`, {
        reason: declineReason.trim() || null,
      });
      toast.success("Declined with a note.");
      setDeclineFor(null);
      setDeclineReason("");
      refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not decline.");
    } finally {
      setBusyId(null);
    }
  };

  const totalUnread = data.unread + pending.length;

  return (
    <div className="relative" ref={ref}>
      <button
        data-testid="notifications-btn"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        className="p-2 rounded-lg hover:bg-equine-soft relative transition-colors tap-44"
      >
        <Bell strokeWidth={1.5} className="w-[18px] h-[18px]" />
        {totalUnread > 0 && (
          <span
            data-testid="notifications-unread-dot"
            className="absolute top-1 right-1 min-w-[16px] h-[16px] px-1 rounded-full bg-equine-clay text-white text-[9.5px] font-semibold flex items-center justify-center"
          >
            {totalUnread > 9 ? "9+" : totalUnread}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="notifications-panel"
          className="absolute right-0 mt-2 w-[380px] max-w-[92vw] bg-equine-card border border-equine-hairline rounded-2xl shadow-2xl z-50 overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-equine-hairline">
            <div className="flex items-center gap-2">
              <Inbox className="w-3.5 h-3.5 text-equine-inkSoft" />
              <span className="text-[12px] uppercase tracking-[0.22em] text-equine-inkMuted font-semibold">
                Inbox
              </span>
            </div>
            <div className="flex items-center gap-2">
              {data.unread > 0 && (
                <button
                  data-testid="notifications-mark-all"
                  onClick={markAll}
                  className="text-[11.5px] text-equine-navy hover:underline inline-flex items-center gap-1"
                >
                  <CheckCheck className="w-3 h-3" /> Mark all read
                </button>
              )}
            </div>
          </div>

          <div className="max-h-[480px] overflow-y-auto scrollbar-luxe">
            {/* Pending service requests — admin / manager / trainer only */}
            {canDecide && pending.length > 0 && (
              <div
                data-testid="pending-requests-section"
                className="border-b border-equine-hairline"
              >
                <div className="px-4 pt-3 pb-2 flex items-center gap-2">
                  <MessageSquare className="w-3.5 h-3.5 text-equine-brassLight" />
                  <span className="text-[10.5px] uppercase tracking-[0.22em] text-equine-brassLight font-semibold">
                    Pending requests
                  </span>
                  <span className="text-[11px] text-equine-inkSoft">{pending.length}</span>
                </div>
                {pending.map((sr) => {
                  const isExpanded = declineFor === sr.id;
                  const isBusy = busyId === sr.id;
                  return (
                    <div
                      key={sr.id}
                      data-testid={`pending-request-${sr.id}`}
                      className="px-4 py-3 hairline"
                    >
                      <div className="text-[13px] text-equine-ink leading-snug">
                        <span className="text-equine-brassLight">
                          {REQUEST_TYPE_LABEL[sr.type] || sr.type.replace("_", " ")}
                        </span>
                        {sr.horse_name && ` · ${sr.horse_name}`}
                      </div>
                      {sr.details && (
                        <div className="text-[12px] text-equine-inkMuted mt-1 leading-relaxed">
                          {sr.details}
                        </div>
                      )}
                      <div className="text-[10.5px] text-equine-inkSoft mt-1">
                        {sr.requester_name} · {fmtDate(sr.created_at)}
                      </div>

                      {!isExpanded ? (
                        <div className="mt-2.5 flex items-center gap-2">
                          <button
                            data-testid={`pending-approve-${sr.id}`}
                            onClick={() => approve(sr.id)}
                            disabled={isBusy}
                            className="inline-flex items-center gap-1 text-[11.5px] px-3 py-1.5 rounded-full bg-equine-navy text-white hover:bg-equine-navy/90 tap-44 disabled:opacity-50"
                          >
                            <Check className="w-3 h-3" strokeWidth={2.2} /> Approve
                          </button>
                          <button
                            data-testid={`pending-decline-open-${sr.id}`}
                            onClick={() => openDecline(sr.id)}
                            disabled={isBusy}
                            className="inline-flex items-center gap-1 text-[11.5px] px-3 py-1.5 rounded-full border border-equine-hairline text-equine-inkMuted hover:text-equine-ink hover:border-equine-graphite tap-44 disabled:opacity-50"
                          >
                            <X className="w-3 h-3" strokeWidth={2.2} /> Decline
                          </button>
                        </div>
                      ) : (
                        <div className="mt-2.5 space-y-2" data-testid={`pending-decline-composer-${sr.id}`}>
                          <textarea
                            value={declineReason}
                            onChange={(e) => setDeclineReason(e.target.value)}
                            placeholder="Optional note for the owner (e.g. 'farrier already booked Thursday')"
                            data-testid={`pending-decline-reason-${sr.id}`}
                            rows={2}
                            className="w-full bg-equine-soft border border-equine-graphite/50 rounded-md px-2.5 py-2 text-[12.5px] text-equine-ink focus:border-equine-champagne outline-none resize-y"
                          />
                          <div className="flex items-center justify-end gap-2">
                            <button
                              data-testid={`pending-decline-cancel-${sr.id}`}
                              onClick={cancelDecline}
                              disabled={isBusy}
                              className="text-[11.5px] px-3 py-1.5 text-equine-inkMuted hover:text-equine-ink tap-44 disabled:opacity-50"
                            >
                              Cancel
                            </button>
                            <button
                              data-testid={`pending-decline-submit-${sr.id}`}
                              onClick={submitDecline}
                              disabled={isBusy}
                              className="text-[11.5px] px-3 py-1.5 rounded-full bg-equine-navy text-white hover:bg-equine-navy/90 tap-44 disabled:opacity-50"
                            >
                              {isBusy ? "Sending…" : "Send"}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Inbox — task-event notifications */}
            {data.items.length === 0 && (!canDecide || pending.length === 0) ? (
              <div className="py-10 text-center text-[12.5px] text-equine-inkSoft">
                A quiet inbox. We'll let you know.
              </div>
            ) : (
              data.items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => markOne(n.id)}
                  data-testid={`notification-${n.id}`}
                  className={`w-full text-left px-4 py-3 hairline hover:bg-equine-soft/60 transition-colors ${
                    !n.read_at ? "bg-equine-brass/5" : ""
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.read_at && (
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-equine-brassLight flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] text-equine-ink leading-snug">{n.summary}</div>
                      <div className="text-[11px] text-equine-inkSoft mt-1">
                        {fmtDate(n.occurred_at)} · {fmtTime(n.occurred_at)}
                      </div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="px-4 py-2.5 border-t border-equine-hairline text-right">
            <Link
              to="/settings"
              onClick={() => setOpen(false)}
              className="text-[11.5px] text-equine-inkMuted hover:text-equine-navy"
            >
              Notification preferences →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
