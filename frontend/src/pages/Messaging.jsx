import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Messaging() {
  const [messages, setMessages] = useState([]);
  const [form, setForm] = useState({ subject: "", body: "", visibility: "staff_only" });

  const load = () => api.get("/messages").then((r) => setMessages(r.data));
  useEffect(() => { load(); }, []);

  const send = async (e) => {
    e.preventDefault();
    await api.post("/messages", form);
    setForm({ subject: "", body: "", visibility: "staff_only" });
    load();
  };

  return (
    <div data-testid="messaging-page">
      <PageHeader eyebrow="Communication" title="Messaging" subtitle="Internal messages and announcements with role-based visibility." />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h2 className="font-display text-2xl mb-4">New message</h2>
          <form onSubmit={send} className="space-y-3" data-testid="message-form">
            <input required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Subject" className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2 text-equine-ivory focus:border-equine-champagne outline-none" />
            <textarea required value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} placeholder="Message…" rows={5} className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2 text-equine-ivory focus:border-equine-champagne outline-none" />
            <select value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value })} className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2 text-equine-ivory focus:border-equine-champagne outline-none">
              <option value="staff_only">Staff Only</option>
              <option value="owner_visible">Owner Visible</option>
              <option value="parent_visible">Parent Visible</option>
              <option value="admin_only">Admin Only</option>
            </select>
            <button className="btn-primary w-full" data-testid="message-send">Send</button>
          </form>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="font-display text-2xl mb-4">Inbox</h2>
          {messages.map((m) => (
            <div key={m.id} className="py-4 hairline">
              <div className="flex items-center justify-between mb-1">
                <div className="text-equine-ivory">{m.subject}</div>
                <StatusPill tone="neutral">{m.visibility.replace('_', ' ')}</StatusPill>
              </div>
              <div className="text-[12.5px] text-equine-platinum/60">From {m.from_name} · {fmtDate(m.created_at)}</div>
              <div className="text-equine-silver/80 text-[14px] mt-2">{m.body}</div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
