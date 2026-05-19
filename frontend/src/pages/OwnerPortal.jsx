import React, { useEffect, useMemo, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import CuratedTimeline from "../components/CuratedTimeline";
import { Heart } from "lucide-react";

export default function OwnerPortal() {
  const [horses, setHorses] = useState([]);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState({ horse_id: "", type: "extra_ride", details: "" });
  const [activeHorseId, setActiveHorseId] = useState("");

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

  const activeHorse = useMemo(
    () => horses.find((h) => h.id === activeHorseId),
    [horses, activeHorseId],
  );

  return (
    <div data-testid="owner-portal-page">
      <PageHeader
        eyebrow="Concierge"
        title="Owner Portal"
        subtitle="Curated updates from the barn — medications, vet visits, farrier work, rehab and feeding — all in one calm stream."
      />

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
            <div key={s.id} className="py-3 hairline flex items-center gap-4">
              <div className="flex-1">
                <div className="text-equine-ink">
                  {s.horse_name} — <span className="capitalize">{s.type.replace('_', ' ')}</span>
                </div>
                <div className="text-[12.5px] text-equine-inkMuted">
                  {s.details || "No additional notes"} · {fmtDate(s.created_at)}
                </div>
              </div>
              <StatusPill tone={s.status === "approved" ? "success" : "warning"}>{s.status}</StatusPill>
              {s.status === "pending" && (
                <button
                  onClick={() => approve(s.id)}
                  data-testid={`approve-${s.id}`}
                  className="btn-secondary !py-1.5 !px-4 text-[12.5px]"
                >
                  Approve
                </button>
              )}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
