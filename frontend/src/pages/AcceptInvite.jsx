import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, tokens } from "../lib/api";
import { Logo } from "../components/Logo";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ShieldCheck, AlertTriangle } from "lucide-react";

export default function AcceptInvite() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { setSession } = useAuth();

  useEffect(() => {
    if (!token) { setError("Missing invitation token"); return; }
    api.get(`/invites/verify?token=${encodeURIComponent(token)}`)
      .then((r) => { setInvite(r.data); setFullName(r.data.full_name || ""); })
      .catch((e) => setError(e?.response?.data?.detail || "This invitation link is no longer valid."));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (password.length < 8) return toast.error("Password must be at least 8 characters");
    if (password !== confirm) return toast.error("Passwords don't match");
    setSubmitting(true);
    try {
      const r = await api.post("/invites/accept", { token, password, full_name: fullName });
      tokens.set({ token: r.data.token, refresh_token: r.data.refresh_token });
      if (setSession) setSession(r.data.user);
      toast.success("Welcome to the barn");
      if (r.data.auto_launch_onboarding) {
        navigate("/onboarding", { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not accept invitation");
    } finally { setSubmitting(false); }
  };

  return (
    <div className="min-h-screen w-full grid lg:grid-cols-2 bg-equine-black" data-testid="accept-invite-page">
      <div className="relative hidden lg:block bg-equine-navy">
        <img
          src="https://static.prod-images.emergentagent.com/jobs/137f7c6b-a2e1-41c0-9c38-96d2409d644a/images/3ca3908290d52bc07be0b5f45e2f358fac3cee0e8034aa339d3b62ddac3b3403.png"
          alt="Luxury equestrian arena"
          className="absolute inset-0 w-full h-full object-cover opacity-40"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-equine-navy via-equine-navy/85 to-equine-navyDeep" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12 text-white">
          <Logo onNavy />
          <div className="max-w-md">
            <div className="text-[10.5px] tracking-[0.28em] uppercase text-equine-brassLight font-semibold mb-5">You've been invited</div>
            <h2 className="font-display text-5xl xl:text-6xl leading-[1.05] text-white">
              A seat at the barn awaits.
            </h2>
            <p className="mt-6 text-equine-silver/85 text-[15px] leading-relaxed">
              Set your password to join the team. We'll walk you through a brief concierge setup so you can hit the ground running.
            </p>
          </div>
          <div className="text-[11px] tracking-[0.22em] uppercase text-equine-brassLight/55">© EquineSync · Crafted for elite equestrian operations</div>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-10"><Logo /></div>
          {error && (
            <div className="equine-card p-8 text-center" data-testid="invite-error">
              <AlertTriangle className="mx-auto text-equine-clay mb-3" />
              <h2 className="font-display text-2xl text-equine-ivory mb-2">Invitation unavailable</h2>
              <p className="text-equine-inkMuted text-[14px]">{error}</p>
              <button onClick={() => navigate("/login")} className="btn-secondary mt-6">Go to sign in</button>
            </div>
          )}

          {!error && !invite && <div className="text-equine-platinum/60">Verifying your invitation…</div>}

          {!error && invite && (
            <>
              <div className="label-eyebrow mb-4">Welcome to {invite.barn?.name || "EquineSync"}</div>
              <h1 className="font-display text-4xl text-equine-ivory leading-none">Set your password</h1>
              <p className="mt-3 text-equine-silver/70">
                You've been invited as <span className="text-equine-champagne capitalize">{invite.role.replace('_', ' ')}</span> by <span className="text-equine-ivory">{invite.invited_by_name}</span>.
              </p>

              <form onSubmit={submit} className="mt-8 space-y-5" data-testid="accept-form">
                <div>
                  <label className="label-eyebrow block mb-2">Email</label>
                  <div className="text-[14px] text-equine-silver bg-equine-soft border border-equine-graphite/60 rounded-xl px-4 py-3">{invite.email}</div>
                </div>
                <div>
                  <label className="label-eyebrow block mb-2">Full name</label>
                  <input value={fullName} onChange={(e) => setFullName(e.target.value)} required data-testid="accept-name"
                    className="w-full bg-equine-soft border border-equine-graphite/60 rounded-xl px-4 py-3 text-equine-ivory focus:outline-none focus:border-equine-champagne" />
                </div>
                <div>
                  <label className="label-eyebrow block mb-2">New password</label>
                  <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} data-testid="accept-password"
                    className="w-full bg-equine-soft border border-equine-graphite/60 rounded-xl px-4 py-3 text-equine-ivory focus:outline-none focus:border-equine-champagne" />
                </div>
                <div>
                  <label className="label-eyebrow block mb-2">Confirm password</label>
                  <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} data-testid="accept-confirm"
                    className="w-full bg-equine-soft border border-equine-graphite/60 rounded-xl px-4 py-3 text-equine-ivory focus:outline-none focus:border-equine-champagne" />
                </div>
                <button disabled={submitting} data-testid="accept-submit" className="btn-primary w-full disabled:opacity-60 inline-flex items-center justify-center gap-2">
                  <ShieldCheck className="w-4 h-4" /> {submitting ? "Setting up…" : "Accept & enter the barn"}
                </button>
                <div className="text-[11px] text-equine-platinum/60 text-center">This invitation expires on {new Date(invite.expires_at).toLocaleDateString()}.</div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
