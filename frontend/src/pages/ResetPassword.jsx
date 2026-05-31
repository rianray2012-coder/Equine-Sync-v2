import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Logo } from "../components/Logo";
import { ShieldCheck, AlertTriangle, CheckCircle2 } from "lucide-react";

// Brand Guide 22 palette — scoped to this auth page.
const C = {
  graphite: "#232734",
  navy: "#2E3550",
  frost: "#F7F8FA",
  mist: "#E3E6EB",
  lilac: "#B8AECF",
  muted: "#98A2B3",
  field: "#1E2230",
  border: "#39415C",
};
const serif = { fontFamily: "'Cormorant Garamond', Georgia, serif" };

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [status, setStatus] = useState("form"); // form | success | error
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!token) { setError("This reset link is missing its token."); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { setError("Passwords don't match."); return; }
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: password });
      setStatus("success");
    } catch (err) {
      setError(err?.response?.data?.detail || "This reset link is invalid or has expired.");
      setStatus("error");
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle = {
    background: C.field, border: `1px solid ${C.border}`, color: C.frost,
  };

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center px-6 py-12"
      style={{ background: `linear-gradient(160deg, ${C.graphite} 0%, ${C.navy} 100%)`, fontFamily: "'Inter', sans-serif" }}
      data-testid="reset-password-page"
    >
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center"><Logo onNavy /></div>

        <div
          className="rounded-2xl p-8 sm:p-10"
          style={{ background: "rgba(46,53,80,0.45)", border: `1px solid ${C.navy}`, boxShadow: "0 2px 24px rgba(35,39,52,0.35)" }}
        >
          {status === "success" ? (
            <div className="text-center" data-testid="reset-success">
              <CheckCircle2 className="mx-auto mb-4" style={{ color: C.lilac }} size={40} />
              <h1 className="text-3xl mb-3" style={{ ...serif, color: C.frost }}>Password updated</h1>
              <p className="text-sm mb-8" style={{ color: C.muted }}>
                Your password has been changed and all existing sessions were signed out. You can now sign in with your new password.
              </p>
              <button
                onClick={() => navigate("/login")}
                data-testid="reset-goto-login"
                className="w-full rounded-full py-3 text-sm font-semibold transition-opacity hover:opacity-90"
                style={{ background: C.lilac, color: C.graphite }}
              >
                Go to sign in
              </button>
            </div>
          ) : (
            <>
              <div className="text-[11px] tracking-[0.28em] uppercase mb-3" style={{ color: C.lilac }}>Password reset</div>
              <h1 className="text-4xl mb-2" style={{ ...serif, color: C.frost }}>Set a new password</h1>
              <p className="text-sm mb-7" style={{ color: C.muted }}>Choose a strong password for your EquineSync account.</p>

              <form onSubmit={submit} className="space-y-5" data-testid="reset-form">
                <div>
                  <label className="block text-[11px] tracking-[0.18em] uppercase mb-2" style={{ color: C.mist }}>New password</label>
                  <input
                    type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                    required minLength={8} autoFocus data-testid="reset-password-input"
                    className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none" style={inputStyle}
                  />
                </div>
                <div>
                  <label className="block text-[11px] tracking-[0.18em] uppercase mb-2" style={{ color: C.mist }}>Confirm password</label>
                  <input
                    type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                    required minLength={8} data-testid="reset-confirm-input"
                    className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none" style={inputStyle}
                  />
                </div>

                {error && (
                  <div className="flex items-start gap-2 text-sm" style={{ color: "#E2A8A8" }} data-testid="reset-error">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" /> <span>{error}</span>
                  </div>
                )}

                <button
                  type="submit" disabled={submitting} data-testid="reset-submit"
                  className="w-full rounded-full py-3 text-sm font-semibold inline-flex items-center justify-center gap-2 transition-opacity hover:opacity-90 disabled:opacity-60"
                  style={{ background: C.lilac, color: C.graphite }}
                >
                  <ShieldCheck size={16} /> {submitting ? "Updating…" : "Update password"}
                </button>
              </form>

              <button
                onClick={() => navigate("/login")}
                data-testid="reset-back-login"
                className="mt-6 w-full text-center text-xs transition-opacity hover:opacity-80"
                style={{ color: C.muted }}
              >
                Back to sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
