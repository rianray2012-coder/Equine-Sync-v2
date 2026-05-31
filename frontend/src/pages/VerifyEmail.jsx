import React, { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Logo } from "../components/Logo";
import { CheckCircle2, AlertTriangle, MailCheck, Loader2 } from "lucide-react";

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

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token");
  const [status, setStatus] = useState("verifying"); // verifying | success | error
  const [error, setError] = useState("");
  const [resendEmail, setResendEmail] = useState("");
  const [resent, setResent] = useState(false);
  const ran = useRef(false); // guard against React 18 StrictMode double-invoke

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    if (!token) {
      setStatus("error");
      setError("This verification link is missing its token.");
      return;
    }
    api.post("/auth/verify-email", { token })
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setError(err?.response?.data?.detail || "This verification link is invalid or has expired.");
      });
  }, [token]);

  const resend = async (e) => {
    e.preventDefault();
    try {
      await api.post("/auth/resend-verification", { email: resendEmail });
    } catch {
      // Uniform response — never reveal whether the account exists.
    } finally {
      setResent(true);
    }
  };

  const inputStyle = { background: C.field, border: `1px solid ${C.border}`, color: C.frost };

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center px-6 py-12"
      style={{ background: `linear-gradient(160deg, ${C.graphite} 0%, ${C.navy} 100%)`, fontFamily: "'Inter', sans-serif" }}
      data-testid="verify-email-page"
    >
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center"><Logo onNavy /></div>

        <div
          className="rounded-2xl p-8 sm:p-10 text-center"
          style={{ background: "rgba(46,53,80,0.45)", border: `1px solid ${C.navy}`, boxShadow: "0 2px 24px rgba(35,39,52,0.35)" }}
        >
          {status === "verifying" && (
            <div data-testid="verify-loading">
              <Loader2 className="mx-auto mb-4 animate-spin" style={{ color: C.lilac }} size={36} />
              <h1 className="text-3xl mb-2" style={{ ...serif, color: C.frost }}>Confirming your email…</h1>
              <p className="text-sm" style={{ color: C.muted }}>One moment while we verify your link.</p>
            </div>
          )}

          {status === "success" && (
            <div data-testid="verify-success">
              <CheckCircle2 className="mx-auto mb-4" style={{ color: C.lilac }} size={40} />
              <h1 className="text-3xl mb-3" style={{ ...serif, color: C.frost }}>Email confirmed</h1>
              <p className="text-sm mb-8" style={{ color: C.muted }}>
                Thank you — your email address is now verified. You're all set.
              </p>
              <button
                onClick={() => navigate("/login")}
                data-testid="verify-goto-login"
                className="w-full rounded-full py-3 text-sm font-semibold transition-opacity hover:opacity-90"
                style={{ background: C.lilac, color: C.graphite }}
              >
                Continue to sign in
              </button>
            </div>
          )}

          {status === "error" && (
            <div data-testid="verify-error">
              <AlertTriangle className="mx-auto mb-4" style={{ color: "#E2A8A8" }} size={38} />
              <h1 className="text-3xl mb-3" style={{ ...serif, color: C.frost }}>Link unavailable</h1>
              <p className="text-sm mb-7" style={{ color: C.muted }}>{error}</p>

              {resent ? (
                <div className="flex items-center justify-center gap-2 text-sm" style={{ color: C.lilac }} data-testid="verify-resent">
                  <MailCheck size={16} /> If an account exists and is unverified, a new link is on its way.
                </div>
              ) : (
                <form onSubmit={resend} className="space-y-3 text-left" data-testid="verify-resend-form">
                  <label className="block text-[11px] tracking-[0.18em] uppercase" style={{ color: C.mist }}>
                    Resend verification email
                  </label>
                  <input
                    type="email" value={resendEmail} onChange={(e) => setResendEmail(e.target.value)}
                    required placeholder="you@example.com" data-testid="verify-resend-email"
                    className="w-full rounded-xl px-4 py-3 text-sm focus:outline-none" style={inputStyle}
                  />
                  <button
                    type="submit" data-testid="verify-resend-submit"
                    className="w-full rounded-full py-3 text-sm font-semibold transition-opacity hover:opacity-90"
                    style={{ background: C.lilac, color: C.graphite }}
                  >
                    Send a new link
                  </button>
                </form>
              )}

              <button
                onClick={() => navigate("/login")}
                data-testid="verify-back-login"
                className="mt-6 w-full text-center text-xs transition-opacity hover:opacity-80"
                style={{ color: C.muted }}
              >
                Back to sign in
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
