import React, { useEffect, useState } from "react";
import { api, track } from "../../lib/api";
import { toast } from "sonner";
import { StatusPill } from "../Primitives";
import {
  Send, Trash2, AlertTriangle, Copy, X,
} from "lucide-react";
import { Field, Select } from "./FormPrimitives";

const ROLE_OPTIONS = [
  { v: "barn_manager",    l: "Barn Manager" },
  { v: "trainer",         l: "Trainer" },
  { v: "groom",           l: "Groom" },
  { v: "working_student", l: "Working Student" },
  { v: "horse_owner",     l: "Horse Owner" },
  { v: "parent",          l: "Parent / Guardian" },
  { v: "veterinarian",    l: "Veterinarian" },
  { v: "farrier",         l: "Farrier" },
  { v: "admin",           l: "Admin" },
];

const StaffStep = ({ onAnyChange }) => {
  const [invites, setInvites] = useState([]);
  const [form, setForm] = useState({ email: "", full_name: "", role: "trainer" });
  const [sending, setSending] = useState(false);
  const [lastDevLink, setLastDevLink] = useState(null);

  const load = () => api.get("/invites").then((r) => setInvites(r.data)).catch(() => setInvites([]));
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.email || !form.role) { toast.error("Email and role required"); return; }
    setSending(true);
    try {
      const r = await api.post("/invites", form);
      toast.success("Invitation sent");
      if (r.data.dev_accept_url) setLastDevLink({ url: r.data.dev_accept_url, email: form.email });
      else setLastDevLink(null);
      setForm({ email: "", full_name: "", role: "trainer" });
      load();
      onAnyChange();
      track("onboarding.invite_sent", { role: r.data.role });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not send invitation");
    } finally {
      setSending(false);
    }
  };

  const resend = async (id) => {
    try {
      const r = await api.post(`/invites/${id}/resend`);
      toast.success("Reminder sent");
      if (r.data.dev_accept_url) setLastDevLink({ url: r.data.dev_accept_url, email: r.data.email });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const revoke = async (id) => {
    if (!window.confirm("Revoke this invitation?")) return;
    await api.post(`/invites/${id}/revoke`);
    toast.success("Invitation revoked");
    load();
  };

  const copy = (text) => { navigator.clipboard?.writeText(text); toast.success("Link copied"); };

  return (
    <div data-testid="step-staff">
      <p className="text-equine-silver/70 text-[14px] mb-5">
        Invite barn managers, trainers, grooms, vets, parents and owners. Each invitee receives a private magic link to set their password — no signups required.
        Roles with setup permissions (Owner / Barn Manager) will be guided through this concierge automatically on first login.
      </p>

      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <Field label="Full name" value={form.full_name}
               onChange={(v) => setForm({ ...form, full_name: v })}
               testid="staff-name" placeholder="Marcus Aldridge" />
        <Field label="Email" type="email" value={form.email}
               onChange={(v) => setForm({ ...form, email: v })}
               testid="staff-email" placeholder="marcus@…" />
        <Select label="Role" value={form.role}
                onChange={(v) => setForm({ ...form, role: v })}
                testid="staff-role" options={ROLE_OPTIONS} />
        <div className="md:col-span-3">
          <button disabled={sending} className="btn-primary inline-flex items-center gap-2" data-testid="staff-invite">
            <Send className="w-4 h-4" /> {sending ? "Sending…" : "Send invitation"}
          </button>
        </div>
      </form>

      {lastDevLink && (
        <div className="mb-5 p-4 rounded-xl bg-equine-amber/10 border border-equine-amber/40" data-testid="dev-link-banner">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-equine-amber mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[12.5px] text-equine-amber font-medium mb-1">Email delivery is in dev mode</div>
              <div className="text-[12px] text-equine-platinum/70 mb-2">
                Add a Resend API key to backend/.env to enable real email. For now, copy this magic link and share it with{" "}
                <strong className="text-equine-ivory">{lastDevLink.email}</strong>:
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate bg-equine-card px-3 py-2 rounded-lg text-[11.5px] text-equine-champagne font-mono">
                  {lastDevLink.url}
                </code>
                <button onClick={() => copy(lastDevLink.url)} className="btn-secondary !py-1.5 !px-3 text-[12px] inline-flex items-center gap-1">
                  <Copy className="w-3.5 h-3.5" /> Copy
                </button>
              </div>
            </div>
            <button onClick={() => setLastDevLink(null)} className="text-equine-platinum/60 hover:text-equine-ivory">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="label-eyebrow mb-2">Sent invitations · {invites.length}</div>
      <div className="space-y-2">
        {invites.length === 0 && <div className="text-equine-platinum/60 text-sm py-3">No invitations yet.</div>}
        {invites.map((iv) => {
          const tone = iv.status === "accepted" ? "success"
            : iv.status === "revoked" || iv.status === "expired" ? "neutral"
            : "info";
          return (
            <div key={iv.id} className="flex items-center gap-3 py-3 px-4 rounded-lg bg-equine-soft border border-equine-graphite/40">
              <div className="flex-1 min-w-0">
                <div className="text-equine-silver text-[13.5px] truncate">{iv.full_name || iv.email}</div>
                <div className="text-[11.5px] text-equine-platinum/60 capitalize truncate">
                  {iv.role.replace("_", " ")} · {iv.email}
                </div>
              </div>
              <StatusPill tone={tone}>{iv.status}</StatusPill>
              {iv.status === "pending" && (
                <>
                  <button onClick={() => resend(iv.id)} data-testid={`invite-resend-${iv.id}`}
                          className="text-equine-platinum/60 hover:text-equine-champagne p-1.5" title="Resend">
                    <Send className="w-4 h-4" />
                  </button>
                  <button onClick={() => revoke(iv.id)} data-testid={`invite-revoke-${iv.id}`}
                          className="text-equine-platinum/60 hover:text-equine-clay p-1.5" title="Revoke">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default StaffStep;
