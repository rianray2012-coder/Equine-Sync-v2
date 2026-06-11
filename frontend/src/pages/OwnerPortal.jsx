import React, { useEffect, useMemo, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Logo } from "../components/Logo";
import CuratedTimeline from "../components/CuratedTimeline";
import OwnerDigestCard from "../components/OwnerDigestCard";
import OwnerUpdatesFeed from "../components/OwnerUpdatesFeed";
import OwnerBillingCard from "../components/OwnerBillingCard";
import OwnerUpcomingCard from "../components/OwnerUpcomingCard";
import { useAuth } from "../context/AuthContext";
import { Heart, X, Check } from "lucide-react";
import { toast } from "sonner";

export default function OwnerPortal() {
  const { user } = useAuth();
  const isOwner = user?.role === "horse_owner";
  const canDecide = ["admin", "barn_manager", "trainer"].includes(user?.role);

  const [horses, setHorses] = useState([]);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState({ horse_id: "", type: "extra_ride", details: "" });
  const [activeHorseId, setActiveHorseId] = useState("");
  const [declineFor, setDeclineFor] = useState(null);
  const [declineReason, setDeclineReason] = useState("");
  const [submittingDecline, setSubmittingDecline] = useState(false);

  const load = () => {
    api.get("/horses").then((r) => {
      setHorses(r.data);
      if (r.data?.length && !activeHorseId) setActiveHorseId(r.data[0].id);
    });
    api.get("/service-requests").then((r) => setRequests(r.data));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.horse_id) return;
    await api.post("/service-requests", form);
    setForm({ horse_id: "", type: "extra_ride", details: "" });
    load();
  };

  const approve = async (id) => {
    await api.post(`/service-requests/${id}/approve`);
    load();
  };

  const openDecline = (sr) => {
    setDeclineFor(sr);
    setDeclineReason("");
  };

  const submitDecline = async () => {
    if (!declineFor) return;
    setSubmittingDecline(true);
    try {
      await api.post(`/service-requests/${declineFor.id}/decline`, {
        reason: declineReason.trim() || null,
      });
      toast.success("Request declined with a thoughtful note.");
      setDeclineFor(null);
      load();
    } catch {
      toast.error("Could not decline this request.");
    } finally {
      setSubmittingDecline(false);
    }
  };

  const activeHorse = useMemo(
    () => horses.find((h) => h.id === activeHorseId),
    [horses, activeHorseId],
  );

  return (
    <div data-testid="owner-portal-page">
      <div className="mb-5"><Logo size={28} /></div>
      <PageHeader
        eyebrow="Concierge"
        title="Owner Portal"
        subtitle="Curated updates from the barn — medications, vet visits, farrier work, rehab and feeding — all in one calm stream."
      />

      {/* ───── Daily Digest (owner only) ───────────────────────────────── */}
      {isOwner && <OwnerDigestCard />}

      {/* ───── Updates from your barn (owner only) — Phase 7C-1 ─────────── */}
      {isOwner && <OwnerUpdatesFeed horses={horses} />}

      {/* ───── Looking ahead (owner only) — Phase 7D-2 ──────────────────── */}
      {isOwner && <OwnerUpcomingCard />}

      {/* ───── Billing (owner only) — Phase 7D-1 ────────────────────────── */}
      {isOwner && <OwnerBillingCard />}

      {/* ───── Curated Timeline ──────────────────────────────────────────── */}
      <Card className="mb-8" data-testid="owner-timeline-card">
        <div className="flex items-center justify-between mb-5 gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
              <Heart strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
            </div>
            <div>
              <h2 className="font-display text-2xl text-equine-ink">Care Timeline</h2>
              <div className="text-[12.5px] text-equine-inkMuted">
                Wellness-focused milestones only. Internal barn workflows stay behind the scenes.
              </div>
            </div>
          </div>
          {horses.length > 1 && (
            <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-luxe">
              {horses.map((h) => (
                <button
                  key={h.id}
                  data-testid={`timeline-horse-${h.id}`}
                  onClick={() => setActiveHorseId(h.id)}
                  className={`shrink-0 px-3 py-1.5 rounded-full text-[12px] tracking-wide border transition-colors ${
                    activeHorseId === h.id
                      ? "bg-equine-navy text-white border-equine-navy"
                      : "bg-equine-card text-equine-inkMuted border-equine-hairline hover:border-equine-graphite"
                  }`}
                >
                  {h.name}
                </button>
              ))}
            </div>
          )}
        </div>
        {activeHorseId ? (
          <CuratedTimeline horseId={activeHorseId} />
        ) : (
          <div className="text-equine-inkSoft text-[13px] py-8 text-center">
            No horses linked yet.
          </div>
        )}
        {activeHorse && (
          <div className="mt-6 pt-5 border-t border-equine-hairline text-[12px] text-equine-inkSoft text-center">
            Viewing care for <span className="text-equine-ink font-medium">{activeHorse.name}</span>
          </div>
        )}
      </Card>

      {/* ───── Concierge form + request log ───────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h2 className="font-display text-2xl mb-4 text-equine-ink">Request a service</h2>
          <form onSubmit={submit} className="space-y-3" data-testid="sr-form">
            <select
              required
              value={form.horse_id}
              onChange={(e) => setForm({ ...form, horse_id: e.target.value })}
              className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2"
            >
              <option value="">Choose horse…</option>
              {horses.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2"
            >
              <option value="extra_ride">Extra Ride</option>
              <option value="grooming">Grooming</option>
              <option value="body_clip">Body Clip</option>
              <option value="hand_walk">Hand Walking</option>
              <option value="lesson">Private Lesson</option>
              <option value="hauling">Hauling</option>
              <option value="show_prep">Show Prep</option>
            </select>
            <textarea
              value={form.details}
              onChange={(e) => setForm({ ...form, details: e.target.value })}
              placeholder="Details / preferences"
              rows={4}
              className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2"
            />
            <button className="btn-primary w-full" data-testid="sr-submit">Submit Request</button>
          </form>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="font-display text-2xl mb-4 text-equine-ink">Recent updates & requests</h2>
          {requests.length === 0 && (
            <div className="text-[13px] text-equine-inkSoft py-6 text-center">
              No requests yet.
            </div>
          )}
          {requests.map((s) => (
            <div key={s.id} className="py-3 hairline flex items-start gap-4 flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <div className="text-equine-ink">
                  {s.horse_name} — <span className="capitalize">{s.type.replace('_', ' ')}</span>
                </div>
                <div className="text-[12.5px] text-equine-inkMuted">
                  {s.details || "No additional notes"} · {fmtDate(s.created_at)}
                </div>
                {s.status === "declined" && s.decline_reason && (
                  <div className="text-[12.5px] text-equine-inkSoft mt-1 italic">
                    Note from the barn: {s.decline_reason}
                  </div>
                )}
              </div>
              <StatusPill tone={
                s.status === "approved" ? "success" :
                s.status === "declined" ? "neutral" : "warning"
              }>{s.status}</StatusPill>
              {s.status === "pending" && canDecide && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => approve(s.id)}
                    data-testid={`approve-${s.id}`}
                    className="btn-secondary !py-1.5 !px-3 text-[12.5px] inline-flex items-center gap-1"
                  >
                    <Check className="w-3.5 h-3.5" /> Approve
                  </button>
                  <button
                    onClick={() => openDecline(s)}
                    data-testid={`decline-${s.id}`}
                    className="!py-1.5 !px-3 text-[12.5px] inline-flex items-center gap-1 rounded-lg border border-equine-hairline text-equine-inkMuted hover:text-equine-ink hover:border-equine-graphite transition-colors"
                  >
                    <X className="w-3.5 h-3.5" /> Decline
                  </button>
                </div>
              )}
            </div>
          ))}
        </Card>
      </div>

      {/* ───── Decline modal ──────────────────────────────────────────── */}
      {declineFor && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-equine-navyDeep/40 backdrop-blur-sm px-4"
          data-testid="decline-modal"
          onClick={(e) => { if (e.target === e.currentTarget) setDeclineFor(null); }}
        >
          <div className="bg-equine-card border border-equine-hairline rounded-2xl shadow-xl max-w-md w-full p-6">
            <div className="uppercase tracking-[0.22em] text-[10.5px] text-equine-inkSoft mb-1">Decline request</div>
            <h3 className="font-display text-xl text-equine-ink mb-1">
              {declineFor.horse_name} · <span className="capitalize">{declineFor.type.replace('_', ' ')}</span>
            </h3>
            <p className="text-[13px] text-equine-inkMuted mb-4">
              Add a brief, owner-facing note (optional). Keep it warm and professional — the owner will see this in their portal.
            </p>
            <textarea
              data-testid="decline-reason-input"
              value={declineReason}
              onChange={(e) => setDeclineReason(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="e.g. Farrier visit scheduled the same morning — we'll book this for next week."
              className="w-full bg-equine-soft border border-equine-hairline rounded-lg px-3 py-2 text-[13.5px] text-equine-ink placeholder:text-equine-inkSoft focus:outline-none focus:border-equine-navy"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setDeclineFor(null)}
                className="px-4 py-2 text-[13px] text-equine-inkMuted hover:text-equine-ink"
              >
                Cancel
              </button>
              <button
                data-testid="decline-confirm-btn"
                onClick={submitDecline}
                disabled={submittingDecline}
                className="btn-primary !py-2 !px-4 text-[13px] disabled:opacity-60"
              >
                {submittingDecline ? "Declining…" : "Decline request"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
