import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { api } from "../lib/api";

const DEMO = [
  { email: "admin@equinesync.com", role: "Stable Owner" },
  { email: "trainer@equinesync.com", role: "Trainer" },
  { email: "groom@equinesync.com", role: "Groom" },
  { email: "owner@equinesync.com", role: "Horse Owner" },
  { email: "vet@equinesync.com", role: "Veterinarian" },
];

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@equinesync.com");
  const [password, setPassword] = useState("demo1234");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotSent, setForgotSent] = useState(false);
  const [forgotLoading, setForgotLoading] = useState(false);

  const sendForgot = async (e) => {
    e.preventDefault();
    setForgotLoading(true);
    try {
      await api.post("/auth/forgot-password", { email: forgotEmail || email });
    } catch {
      // Uniform response — never reveal whether the account exists.
    } finally {
      setForgotSent(true);
      setForgotLoading(false);
    }
  };

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  const submit = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    setErr(""); setLoading(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err2) {
      setErr(err2?.response?.data?.detail || "Sign in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full grid lg:grid-cols-2 bg-equine-black">
      {/* Left visual */}
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
            <div className="text-[10.5px] tracking-[0.28em] uppercase text-equine-brassLight font-semibold mb-5">An operating system for the modern barn</div>
            <h2 className="font-display text-5xl xl:text-6xl leading-[1.05] text-white">
              Quiet precision.<br/>Operational mastery.
            </h2>
            <p className="mt-6 text-equine-silver/85 text-[15px] leading-relaxed">
              EquineSync unites horse care, training, billing, and owner communication in one elegant platform — built for elite show barns, rehab facilities, and luxury private operations.
            </p>
          </div>
          <div className="text-[11px] tracking-[0.22em] uppercase text-equine-brassLight/55">© EquineSync · Crafted for elite equestrian operations</div>
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-10"><Logo /></div>
          <div className="label-eyebrow mb-4">Sign in</div>
          <h1 className="font-display text-4xl text-equine-ivory leading-none">Welcome back</h1>
          <p className="mt-3 text-equine-silver">Access your stable operations dashboard.</p>

          <form onSubmit={submit} className="mt-8 space-y-5" data-testid="login-form">
            <div>
              <label className="label-eyebrow block mb-2">Email</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                data-testid="login-email"
                className="input-field"
              />
            </div>
            <div>
              <label className="label-eyebrow block mb-2">Password</label>
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                data-testid="login-password"
                className="input-field"
              />
              <div className="flex justify-end mt-2">
                <button
                  type="button"
                  onClick={() => { setForgotEmail(email); setShowForgot((v) => !v); setForgotSent(false); }}
                  data-testid="forgot-password-link"
                  className="text-[12px] text-equine-silver hover:text-equine-ivory transition-colors"
                >
                  Forgot your password?
                </button>
              </div>
            </div>
            {err && <div className="text-equine-clay text-sm" data-testid="login-error">{err}</div>}
            <button type="submit" onClick={submit} disabled={loading} data-testid="login-submit"
              className="btn-primary w-full disabled:opacity-60">
              {loading ? "Signing in…" : "Enter the barn"}
            </button>
          </form>

          {showForgot && (
            <div className="mt-5 p-4 rounded-xl border border-equine-graphite/40 bg-equine-soft/40" data-testid="forgot-panel">
              {forgotSent ? (
                <p className="text-[13px] text-equine-silver" data-testid="forgot-sent">
                  If an account exists for that email, a password reset link is on its way. Please check your inbox.
                </p>
              ) : (
                <form onSubmit={sendForgot} className="space-y-3">
                  <div className="label-eyebrow">Reset your password</div>
                  <input
                    type="email" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)}
                    required placeholder="you@example.com" data-testid="forgot-email"
                    className="input-field"
                  />
                  <button
                    type="submit" disabled={forgotLoading} data-testid="forgot-submit"
                    className="btn-primary w-full disabled:opacity-60"
                  >
                    {forgotLoading ? "Sending…" : "Send reset link"}
                  </button>
                </form>
              )}
            </div>
          )}

          <div className="mt-10 pt-6 border-t border-equine-hairline">
            <div className="label-eyebrow mb-3">Demo accounts (password: demo1234)</div>
            <div className="grid grid-cols-1 gap-2">
              {DEMO.map((d) => (
                <button
                  key={d.email}
                  onClick={() => { setEmail(d.email); setPassword("demo1234"); }}
                  data-testid={`demo-${d.role.toLowerCase().replace(/\s/g, '-')}`}
                  className="text-left px-4 py-2.5 rounded-lg border border-equine-graphite/40 hover:border-equine-saddle hover:bg-equine-soft transition-all flex items-center justify-between"
                >
                  <span className="text-[13px] text-equine-ivory">{d.email}</span>
                  <span className="text-[11px] tracking-[0.16em] uppercase text-equine-silver">{d.role}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
