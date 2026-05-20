import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { toast } from "sonner";
import { Field, Select } from "./FormPrimitives";

const FACILITY_TYPES = [
  { v: "private",  l: "Private" },
  { v: "boarding", l: "Boarding" },
  { v: "lesson",   l: "Lesson Program" },
  { v: "training", l: "Training" },
  { v: "show",     l: "Show Barn" },
  { v: "rehab",    l: "Rehab Facility" },
  { v: "rescue",   l: "Rescue" },
];

const BarnStep = ({ onAnyChange }) => {
  const [barn, setBarn] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.get("/barn").then((r) => setBarn(r.data)); }, []);

  const update = (patch) => { setBarn({ ...barn, ...patch }); onAnyChange(); };

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/barn", barn);
      toast.success("Barn profile saved");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!barn) return <div className="text-equine-platinum/60">Loading…</div>;

  return (
    <div className="space-y-5" data-testid="step-barn">
      <p className="text-equine-silver/70 text-[14px]">
        Tell us about your facility. This drives branding, timezone-aware schedules and contact details for owners.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Barn name" value={barn.name} onChange={(v) => update({ name: v })} placeholder="Whitfield Equestrian Estate" testid="barn-name" />
        <Select label="Facility type" value={barn.facility_type} onChange={(v) => update({ facility_type: v })} options={FACILITY_TYPES} testid="barn-type" />
        <Field label="Address" value={barn.address} onChange={(v) => update({ address: v })} placeholder="1200 Whitfield Lane, Wellington FL" testid="barn-address" />
        <Field label="Timezone" value={barn.timezone} onChange={(v) => update({ timezone: v })} placeholder="America/New_York" testid="barn-tz" />
        <Field label="Contact email" type="email" value={barn.contact_email} onChange={(v) => update({ contact_email: v })} placeholder="ops@whitfield.com" testid="barn-email" />
        <Field label="Contact phone" value={barn.contact_phone} onChange={(v) => update({ contact_phone: v })} placeholder="+1 555 0100" testid="barn-phone" />
        <Field label="Logo URL" value={barn.logo_url} onChange={(v) => update({ logo_url: v })} placeholder="https://…" testid="barn-logo" />
        <Field
          label="Disciplines (comma-sep)"
          value={(barn.disciplines || []).join(", ")}
          onChange={(v) => update({ disciplines: v.split(",").map((s) => s.trim()).filter(Boolean) })}
          placeholder="Show Jumping, Dressage, Hunters"
          testid="barn-disc"
        />
      </div>
      <button onClick={save} disabled={saving} className="btn-primary" data-testid="barn-save">
        {saving ? "Saving…" : "Save profile"}
      </button>
    </div>
  );
};

export default BarnStep;
