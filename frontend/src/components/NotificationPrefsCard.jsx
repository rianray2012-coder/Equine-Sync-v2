import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./Primitives";
import { Bell, Mail, Inbox, Sunrise } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";

const EVENT_TYPES = [
  { key: "task.completed", label: "Completed" },
  { key: "task.skipped",   label: "Skipped / Refused" },
  { key: "task.voided",    label: "Reverted" },
];

const CATEGORIES = [
  "medication", "farrier", "vet", "rehab", "feed", "turnout_out", "turnout_in", "stall_clean", "custom",
];

const Toggle = ({ checked, onChange, testid }) => (
  <button
    data-testid={testid}
    onClick={() => onChange(!checked)}
    type="button"
    aria-pressed={checked}
    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
      checked ? "bg-equine-navy" : "bg-equine-graphite/40"
    }`}
  >
    <span
      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform ${
        checked ? "translate-x-5" : "translate-x-1"
      }`}
    />
  </button>
);

export default function NotificationPrefsCard() {
  const { user } = useAuth();
  const isOwner = user?.role === "horse_owner";
  const [prefs, setPrefs] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/notifications/preferences").then((r) => setPrefs(r.data)).catch(() => {});
  }, []);

  if (!prefs) {
    return (
      <Card className="mt-6">
        <div className="text-equine-inkSoft text-[13px]">Loading notification preferences…</div>
      </Card>
    );
  }

  const togglesFor = (channel) => {
    const rules = (channel === "inbox" ? prefs.inbox_rules : prefs.email_rules) || {};
    const get = (et, cat) => {
      const cats = rules[et];
      if (!cats) return false;
      if (cats === "*" || (Array.isArray(cats) && cats.includes("*"))) return true;
      return Array.isArray(cats) ? cats.includes(cat) : false;
    };
    const set = (et, cat, on) => {
      const next = { ...rules };
      const cur = next[et];
      let arr = Array.isArray(cur) ? [...cur] : (typeof cur === "object" ? Array.from(cur || []) : []);
      if (on && !arr.includes(cat)) arr.push(cat);
      if (!on) arr = arr.filter((c) => c !== cat);
      next[et] = arr;
      setPrefs((p) => ({
        ...p,
        [channel === "inbox" ? "inbox_rules" : "email_rules"]: next,
      }));
    };
    return { get, set };
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/notifications/preferences", {
        inbox_enabled: prefs.inbox_enabled,
        email_enabled: prefs.email_enabled,
        push_enabled: false,
        digest_enabled: prefs.digest_enabled,
        inbox_rules: prefs.inbox_rules,
        email_rules: prefs.email_rules,
      });
      toast.success("Preferences saved");
    } catch {
      toast.error("Could not save preferences");
    } finally {
      setSaving(false);
    }
  };

  const inboxT = togglesFor("inbox");
  const emailT = togglesFor("email");

  return (
    <Card className="mt-6" data-testid="notification-prefs-card">
      <div className="flex items-center gap-3 mb-1">
        <Bell strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
        <h3 className="font-display text-2xl text-equine-ink">Notification preferences</h3>
      </div>
      <p className="text-[12.5px] text-equine-inkMuted mb-5 max-w-2xl">
        Choose how the barn reaches you. Inbox lives in your bell · email arrives in your inbox · push is coming soon.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="flex items-center justify-between bg-equine-soft rounded-xl px-4 py-3">
          <div className="flex items-center gap-2">
            <Inbox className="w-3.5 h-3.5 text-equine-navy" />
            <span className="text-[13px] text-equine-ink">In-app inbox</span>
          </div>
          <Toggle
            testid="toggle-inbox-enabled"
            checked={!!prefs.inbox_enabled}
            onChange={(v) => setPrefs((p) => ({ ...p, inbox_enabled: v }))}
          />
        </div>
        <div className="flex items-center justify-between bg-equine-soft rounded-xl px-4 py-3">
          <div className="flex items-center gap-2">
            <Mail className="w-3.5 h-3.5 text-equine-navy" />
            <span className="text-[13px] text-equine-ink">Email</span>
          </div>
          <Toggle
            testid="toggle-email-enabled"
            checked={!!prefs.email_enabled}
            onChange={(v) => setPrefs((p) => ({ ...p, email_enabled: v }))}
          />
        </div>
      </div>

      {isOwner && (
        <div className="bg-equine-soft/70 border border-equine-hairline rounded-xl px-4 py-3.5 mb-6 flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-2 min-w-[220px] flex-1">
            <Sunrise className="w-3.5 h-3.5 text-equine-navy mt-0.5" />
            <div>
              <div className="text-[13px] text-equine-ink">Morning digest</div>
              <div className="text-[11.5px] text-equine-inkMuted max-w-md">
                One calm email each morning summarising your horse&apos;s care. Pause anytime.
              </div>
            </div>
          </div>
          <Toggle
            testid="toggle-digest-enabled"
            checked={prefs.digest_enabled !== false}
            onChange={(v) => setPrefs((p) => ({ ...p, digest_enabled: v }))}
          />
        </div>
      )}

      <div className="overflow-x-auto scrollbar-luxe">
        <table className="w-full text-[12.5px] min-w-[640px]">
          <thead>
            <tr className="text-left text-equine-inkSoft">
              <th className="py-2 pr-4 font-medium uppercase tracking-[0.18em] text-[10.5px]">Event × category</th>
              {CATEGORIES.map((c) => (
                <th key={c} className="py-2 px-1 font-medium uppercase tracking-[0.18em] text-[10px] text-center">
                  {c.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EVENT_TYPES.map((et) => (
              <React.Fragment key={et.key}>
                <tr className="border-t border-equine-hairline">
                  <td className="py-2 pr-4 text-equine-ink">
                    <span className="inline-flex items-center gap-1.5">
                      <Inbox className="w-3 h-3 text-equine-inkSoft" /> {et.label}
                    </span>
                  </td>
                  {CATEGORIES.map((cat) => (
                    <td key={cat} className="py-2 px-1 text-center">
                      <input
                        type="checkbox"
                        data-testid={`pref-inbox-${et.key}-${cat}`}
                        checked={inboxT.get(et.key, cat)}
                        onChange={(e) => inboxT.set(et.key, cat, e.target.checked)}
                      />
                    </td>
                  ))}
                </tr>
                <tr className="border-t border-equine-hairline">
                  <td className="py-2 pr-4 text-equine-inkMuted">
                    <span className="inline-flex items-center gap-1.5">
                      <Mail className="w-3 h-3 text-equine-inkSoft" /> {et.label}
                    </span>
                  </td>
                  {CATEGORIES.map((cat) => (
                    <td key={cat} className="py-2 px-1 text-center">
                      <input
                        type="checkbox"
                        data-testid={`pref-email-${et.key}-${cat}`}
                        checked={emailT.get(et.key, cat)}
                        onChange={(e) => emailT.set(et.key, cat, e.target.checked)}
                      />
                    </td>
                  ))}
                </tr>
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-5 flex justify-end">
        <button
          data-testid="save-notification-prefs"
          onClick={save}
          disabled={saving}
          className="btn-primary"
        >
          {saving ? "Saving…" : "Save preferences"}
        </button>
      </div>
    </Card>
  );
}
