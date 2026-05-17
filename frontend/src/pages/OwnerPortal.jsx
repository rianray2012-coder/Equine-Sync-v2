import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function OwnerPortal() {
  const [horses, setHorses] = useState([]);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState({ horse_id: "", type: "extra_ride", details: "" });

  const load = () => {
    api.get("/horses").then((r) => setHorses(r.data));
    api.get("/service-requests").then((r) => setRequests(r.data));
  };
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.horse_id) return;
    await api.post("/service-requests", form);
    setForm({ horse_id: "", type: "extra_ride", details: "" });
    load();
  };

  const approve = async (id) => { await api.post(`/service-requests/${id}/approve`); load(); };

  return (
    <div data-testid="owner-portal-page">
      <PageHeader eyebrow="Concierge" title="Owner Portal" subtitle="Curated updates, photos, and one-tap service requests for your horse." />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h2 className="font-display text-2xl mb-4">Request a service</h2>
          <form onSubmit={submit} className="space-y-3" data-testid="sr-form">
            <select required value={form.horse_id} onChange={(e) => setForm({ ...form, horse_id: e.target.value })} className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2">
              <option value="">Choose horse…</option>
              {horses.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2">
              <option value="extra_ride">Extra Ride</option>
              <option value="grooming">Grooming</option>
              <option value="body_clip">Body Clip</option>
              <option value="hand_walk">Hand Walking</option>
              <option value="lesson">Private Lesson</option>
              <option value="hauling">Hauling</option>
              <option value="show_prep">Show Prep</option>
            </select>
            <textarea value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} placeholder="Details / preferences" rows={4} className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2" />
            <button className="btn-primary w-full" data-testid="sr-submit">Submit Request</button>
          </form>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="font-display text-2xl mb-4">Recent updates & requests</h2>
          {requests.map((s) => (
            <div key={s.id} className="py-3 hairline flex items-center gap-4">
              <div className="flex-1">
                <div className="text-equine-ivory">{s.horse_name} — <span className="capitalize">{s.type.replace('_', ' ')}</span></div>
                <div className="text-[12.5px] text-equine-platinum/60">{s.details || "No additional notes"} · {fmtDate(s.created_at)}</div>
              </div>
              <StatusPill tone={s.status === "approved" ? "success" : "warning"}>{s.status}</StatusPill>
              {s.status === "pending" && <button onClick={() => approve(s.id)} data-testid={`approve-${s.id}`} className="btn-secondary !py-1.5 !px-4 text-[12.5px]">Approve</button>}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
