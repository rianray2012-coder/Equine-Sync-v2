import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { api } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { RotateCcw, Trash2, ShieldAlert } from "lucide-react";
import NotificationPrefsCard from "../components/NotificationPrefsCard";

export default function Settings() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [resetting, setResetting] = useState(false);
  const [wiping, setWiping] = useState(false);
  const isAdmin = user?.role === "admin";

  const reopenSetup = async () => {
    setResetting(true);
    try {
      await api.post("/onboarding/reset");
      toast.success("Setup re-opened");
      navigate("/onboarding");
    } catch { toast.error("Could not reset"); }
    finally { setResetting(false); }
  };

  const tenantReset = async (scope) => {
    const confirmMsg = scope === "all_setup_data"
      ? 'This will DELETE all locations, feed templates, inventory, schedules, staff invites AND onboarding progress for every user. Type "RESET" to confirm.'
      : 'This will reset onboarding progress for all users (data preserved). Type "RESET" to confirm.';
    const answer = window.prompt(confirmMsg);
    if (answer !== "RESET") { if (answer !== null) toast.error("Confirmation didn't match"); return; }
    setWiping(true);
    try {
      const r = await api.post("/admin/tenant-reset", { scope, confirm: "RESET" });
      toast.success(`Reset complete: ${Object.entries(r.data.cleared).map(([k, v]) => `${k}=${v}`).join(", ")}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reset failed");
    } finally { setWiping(false); }
  };

  return (
    <div data-testid="settings-page">
      <PageHeader eyebrow="Account" title="Settings" subtitle="Account, facility, and team preferences." />
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><div className="label-eyebrow">Name</div><div className="text-equine-ivory mt-1">{user?.full_name}</div></div>
          <div><div className="label-eyebrow">Email</div><div className="text-equine-ivory mt-1">{user?.email}</div></div>
          <div><div className="label-eyebrow">Role</div><div className="text-equine-ivory mt-1 capitalize">{user?.role?.replace('_', ' ')}</div></div>
          <div><div className="label-eyebrow">Facility</div><div className="text-equine-ivory mt-1">Whitfield Equestrian Estate</div></div>
        </div>
      </Card>

      <Card className="mt-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-[260px]">
            <div className="label-eyebrow">Setup Concierge</div>
            <h3 className="font-display text-2xl text-equine-ivory mt-1">Re-open barn setup wizard</h3>
            <p className="text-equine-silver/70 text-[13.5px] mt-2 max-w-xl">
              Restart the 10-step guided onboarding to add another barn, refresh templates, or correct configuration. Existing data (horses, owners, etc.) is preserved.
            </p>
          </div>
          <button onClick={reopenSetup} disabled={resetting} data-testid="reopen-setup" className="btn-secondary inline-flex items-center gap-2 whitespace-nowrap">
            <RotateCcw className="w-4 h-4" /> {resetting ? "Opening…" : "Re-open setup"}
          </button>
        </div>
      </Card>

      <NotificationPrefsCard />

      {isAdmin && (
        <Card className="mt-6 !border-equine-clay/30">
          <div className="flex items-start gap-3 mb-3">
            <ShieldAlert strokeWidth={1.4} className="text-equine-clay flex-shrink-0 mt-0.5" />
            <div>
              <StatusPill tone="critical">Admin only</StatusPill>
              <h3 className="font-display text-2xl text-equine-ivory mt-2">Tenant-level reset</h3>
              <p className="text-equine-silver/70 text-[13.5px] mt-2 max-w-2xl">
                For support recovery. Use with care — actions cannot be undone. Operational data (horses, vet records, billing) is never touched by these tools.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
            <button onClick={() => tenantReset("onboarding")} disabled={wiping} data-testid="tenant-reset-onboarding"
              className="btn-secondary text-left p-4 h-auto flex items-start gap-3 disabled:opacity-50 hover:border-equine-amber/60">
              <RotateCcw className="w-4 h-4 mt-0.5 text-equine-amber flex-shrink-0" />
              <div>
                <div className="text-[13px] text-equine-ivory">Reset onboarding for all users</div>
                <div className="text-[11.5px] text-equine-platinum/60 mt-0.5">Wizard re-opens at step 1; setup data preserved.</div>
              </div>
            </button>
            <button onClick={() => tenantReset("all_setup_data")} disabled={wiping} data-testid="tenant-reset-all"
              className="btn-secondary text-left p-4 h-auto flex items-start gap-3 disabled:opacity-50 hover:border-equine-clay/60">
              <Trash2 className="w-4 h-4 mt-0.5 text-equine-clay flex-shrink-0" />
              <div>
                <div className="text-[13px] text-equine-ivory">Wipe all setup data</div>
                <div className="text-[11.5px] text-equine-platinum/60 mt-0.5">Deletes barn profile, locations, templates, inventory, schedules, invites.</div>
              </div>
            </button>
          </div>
        </Card>
      )}
    </div>
  );
}
