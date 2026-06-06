import React, { useEffect, useState } from "react";
import { api, fmtDate } from "../lib/api";
import { Card, StatusPill } from "./Primitives";
import { Megaphone, Pencil, Send, Upload, Archive, Loader2 } from "lucide-react";
import { toast } from "sonner";

/**
 * Phase 7C-2 — staff composer for Owner Updates, scoped to one horse.
 *
 * Rendered on the HorseProfile "Updates" tab for {admin, barn_manager, trainer}.
 * Drives the author lifecycle only: create draft -> edit -> publish (non-sensitive)
 * / submit (sensitive) -> archive. Review actions (approve / request-changes) are
 * intentionally NOT here — those belong to 7C-3 (manager review queue).
 */
const KINDS = ["routine", "training", "wellness", "incident", "billing", "recap"];
const VISIBILITIES = ["owner_facing", "internal"];

const STATUS_TONE = {
  draft: "neutral",
  pending_review: "warning",
  published: "success",
  archived: "neutral",
};

const EMPTY_FORM = { kind: "routine", visibility: "owner_facing", body: "", sensitive: false };

const Select = ({ value, onChange, options, testid }) => (
  <select
    data-testid={testid}
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className="bg-equine-soft border border-equine-steel/40 rounded-lg px-3 py-2 text-[13px] text-equine-ivory capitalize"
  >
    {options.map((o) => (
      <option key={o} value={o}>{o.replace("_", " ")}</option>
    ))}
  </select>
);

export default function HorseOwnerUpdates({ horseId }) {
  const [items, setItems] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY_FORM);
  const [busyId, setBusyId] = useState(null);

  const load = () => {
    api
      .get(`/owner-updates?horse_id=${horseId}`)
      .then((r) => setItems(Array.isArray(r.data) ? r.data : []))
      .catch(() => setItems([]));
  };
  useEffect(load, [horseId]);

  const create = async (e) => {
    e.preventDefault();
    if (!form.body.trim()) return;
    setSaving(true);
    try {
      await api.post("/owner-updates", { horse_id: horseId, ...form, body: form.body.trim() });
      setForm(EMPTY_FORM);
      toast.success("Draft saved.");
      load();
    } catch {
      toast.error("Could not save the draft.");
    } finally {
      setSaving(false);
    }
  };

  const act = async (id, verb, label) => {
    setBusyId(id);
    try {
      await api.post(`/owner-updates/${id}/${verb}`);
      toast.success(label);
      load();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(detail || "Action failed.");
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (u) => {
    setEditId(u.id);
    setEditForm({ kind: u.kind, visibility: u.visibility, body: u.body, sensitive: !!u.sensitive });
  };

  const saveEdit = async (id) => {
    setBusyId(id);
    try {
      await api.patch(`/owner-updates/${id}`, { ...editForm, body: editForm.body.trim() });
      setEditId(null);
      toast.success("Draft updated.");
      load();
    } catch {
      toast.error("Could not update the draft.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div data-testid="horse-owner-updates">
      {/* ───── Composer ───── */}
      <Card className="mb-6" data-testid="updates-composer">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-equine-soft flex items-center justify-center">
            <Megaphone strokeWidth={1.5} className="w-4 h-4 text-equine-champagne" />
          </div>
          <div>
            <h3 className="font-display text-xl text-equine-ivory">New owner update</h3>
            <div className="text-[12px] text-equine-platinum/60">
              A note for this horse&apos;s owner. Drafts stay private until published.
            </div>
          </div>
        </div>
        <form onSubmit={create} className="space-y-3">
          <div className="flex gap-3 flex-wrap">
            <Select value={form.kind} onChange={(v) => setForm({ ...form, kind: v })} options={KINDS} testid="composer-kind" />
            <Select value={form.visibility} onChange={(v) => setForm({ ...form, visibility: v })} options={VISIBILITIES} testid="composer-visibility" />
          </div>
          <textarea
            data-testid="composer-body"
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            rows={4}
            placeholder="Write a calm, clear update the owner will appreciate…"
            className="w-full bg-equine-soft border border-equine-steel/40 rounded-lg px-3 py-2 text-[13.5px] text-equine-ivory placeholder:text-equine-platinum/40 focus:outline-none focus:border-equine-champagne"
          />
          <label className="flex items-center gap-2 text-[13px] text-equine-platinum/80 cursor-pointer">
            <input
              type="checkbox"
              data-testid="composer-sensitive"
              checked={form.sensitive}
              onChange={(e) => setForm({ ...form, sensitive: e.target.checked })}
              className="accent-equine-champagne"
            />
            Mark as sensitive
          </label>
          {form.sensitive && (
            <div className="text-[12px] text-equine-champagne/80" data-testid="composer-sensitive-hint">
              Sensitive updates go to a manager for review before owners see them.
            </div>
          )}
          <div className="flex justify-end">
            <button type="submit" disabled={saving || !form.body.trim()} className="btn-primary !py-2 !px-4 text-[13px] disabled:opacity-50" data-testid="composer-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save draft"}
            </button>
          </div>
        </form>
      </Card>

      {/* ───── List ───── */}
      {items === null && (
        <div className="py-8 text-center text-equine-platinum/50 text-[13px]">Loading updates…</div>
      )}
      {items !== null && items.length === 0 && (
        <div className="py-8 text-center text-equine-platinum/50 text-[13px]" data-testid="updates-empty">
          No updates yet for this horse.
        </div>
      )}
      {items !== null && items.length > 0 && (
        <div className="space-y-3">
          {items.map((u) => {
            const isEditing = editId === u.id;
            const busy = busyId === u.id;
            return (
              <Card key={u.id} hover={false} data-testid={`owner-update-row-${u.id}`}>
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <StatusPill tone={STATUS_TONE[u.status] || "neutral"}>
                    {u.status === "pending_review" ? "awaiting review" : u.status}
                  </StatusPill>
                  <span className="text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full bg-equine-soft border border-equine-steel/30 text-equine-platinum/70 capitalize">{u.kind}</span>
                  <span className="text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full bg-equine-soft border border-equine-steel/30 text-equine-platinum/70">{u.visibility.replace("_", " ")}</span>
                  {u.sensitive && <span className="text-[10px] uppercase tracking-[0.18em] text-equine-champagne/80">sensitive</span>}
                  <span className="ml-auto text-[11px] text-equine-platinum/40">{fmtDate(u.created_at)}</span>
                </div>

                {isEditing ? (
                  <div className="space-y-2">
                    <div className="flex gap-3 flex-wrap">
                      <Select value={editForm.kind} onChange={(v) => setEditForm({ ...editForm, kind: v })} options={KINDS} testid={`edit-kind-${u.id}`} />
                      <Select value={editForm.visibility} onChange={(v) => setEditForm({ ...editForm, visibility: v })} options={VISIBILITIES} testid={`edit-visibility-${u.id}`} />
                      <label className="flex items-center gap-2 text-[12px] text-equine-platinum/80">
                        <input type="checkbox" checked={editForm.sensitive} onChange={(e) => setEditForm({ ...editForm, sensitive: e.target.checked })} className="accent-equine-champagne" data-testid={`edit-sensitive-${u.id}`} />
                        sensitive
                      </label>
                    </div>
                    <textarea
                      data-testid={`edit-body-${u.id}`}
                      value={editForm.body}
                      onChange={(e) => setEditForm({ ...editForm, body: e.target.value })}
                      rows={3}
                      className="w-full bg-equine-soft border border-equine-steel/40 rounded-lg px-3 py-2 text-[13px] text-equine-ivory"
                    />
                    <div className="flex gap-2 justify-end">
                      <button onClick={() => setEditId(null)} className="text-[12.5px] text-equine-platinum/60 hover:text-equine-ivory px-3 py-1.5">Cancel</button>
                      <button onClick={() => saveEdit(u.id)} disabled={busy || !editForm.body.trim()} className="btn-primary !py-1.5 !px-3 text-[12.5px] disabled:opacity-50" data-testid={`edit-save-${u.id}`}>Save</button>
                    </div>
                  </div>
                ) : (
                  <p className="text-[13.5px] text-equine-silver/85 leading-relaxed whitespace-pre-line">{u.body}</p>
                )}

                {!isEditing && u.status === "draft" && (
                  <div className="flex gap-2 mt-3 flex-wrap">
                    <RowBtn testid={`update-edit-${u.id}`} onClick={() => startEdit(u)} icon={Pencil} label="Edit" />
                    <RowBtn testid={`update-submit-${u.id}`} onClick={() => act(u.id, "submit", "Submitted for review.")} icon={Send} label="Submit for review" busy={busy} />
                    {!u.sensitive && (
                      <RowBtn testid={`update-publish-${u.id}`} onClick={() => act(u.id, "publish", "Published to the owner.")} icon={Upload} label="Publish" busy={busy} primary />
                    )}
                  </div>
                )}
                {!isEditing && u.status === "published" && (
                  <div className="flex gap-2 mt-3">
                    <RowBtn testid={`update-archive-${u.id}`} onClick={() => act(u.id, "archive", "Update archived.")} icon={Archive} label="Archive" busy={busy} />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

const RowBtn = ({ testid, onClick, icon: Icon, label, busy, primary }) => (
  <button
    data-testid={testid}
    onClick={onClick}
    disabled={busy}
    className={`inline-flex items-center gap-1.5 !py-1.5 !px-3 text-[12.5px] rounded-lg transition-colors disabled:opacity-50 ${
      primary
        ? "btn-primary"
        : "border border-equine-steel/40 text-equine-platinum/80 hover:text-equine-ivory hover:border-equine-champagne"
    }`}
  >
    {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />} {label}
  </button>
);
