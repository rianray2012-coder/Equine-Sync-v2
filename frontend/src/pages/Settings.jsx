import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, PageHeader } from "../components/Primitives";
import { api } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { RotateCcw } from "lucide-react";

export default function Settings() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [resetting, setResetting] = useState(false);

  const reopenSetup = async () => {
    setResetting(true);
    try {
      await api.post("/onboarding/reset");
      toast.success("Setup re-opened");
      navigate("/onboarding");
    } catch { toast.error("Could not reset"); }
    finally { setResetting(false); }
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
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="label-eyebrow">Setup Concierge</div>
            <h3 className="font-display text-2xl text-equine-ivory mt-1">Re-open barn setup wizard</h3>
            <p className="text-equine-silver/70 text-[13.5px] mt-2 max-w-xl">
              Restart the 10-step guided onboarding to add another barn, refresh templates, or correct configuration. Your existing data (horses, owners, etc.) is preserved.
            </p>
          </div>
          <button onClick={reopenSetup} disabled={resetting} data-testid="reopen-setup" className="btn-secondary inline-flex items-center gap-2 whitespace-nowrap">
            <RotateCcw className="w-4 h-4" /> {resetting ? "Opening…" : "Re-open setup"}
          </button>
        </div>
      </Card>
    </div>
  );
}
