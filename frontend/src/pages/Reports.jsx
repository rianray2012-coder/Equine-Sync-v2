import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Logo } from "../components/Logo";
import { BrandLoader } from "../components/BrandLoader";
import { Sparkles, Send, Clock, TrendingUp, CheckCircle2, Mail, AlertTriangle, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function Reports() {
  const [health, setHealth] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [days, setDays] = useState(3);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [h, c] = await Promise.all([
        api.get("/reports/setup-health"),
        api.get(`/reports/nudge-candidates?min_days=${days}`),
      ]);
      setHealth(h.data);
      setCandidates(c.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not load reports");
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [days]);

  const runNudges = async () => {
    if (!candidates.length) { toast.info("No stalled users to nudge right now."); return; }
    setRunning(true);
    try {
      const r = await api.post("/admin/send-nudges", { min_days: days, cooldown_hours: 24 });
      setLastRun(r.data);
      const noun = r.data.sent === 1 ? "reminder" : "reminders";
      if (r.data.sent > 0) toast.success(`Sent ${r.data.sent} ${noun}`);
      else if (r.data.skipped > 0) toast.info(`${r.data.skipped} skipped (cooldown or sandbox)`);
      else toast.warning(`${r.data.errors} delivery errors`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Send failed");
    } finally { setRunning(false); }
  };

  return (
    <div data-testid="reports-page">
      <div className="mb-4"><Logo variant="icon" size={26} /></div>
      <PageHeader
        eyebrow="Operations · Setup Health"
        title="Onboarding Reports"
        subtitle="Track how new barns are activating, where users get stuck, and send personalised nudges to anyone who's stalled."
        action={
          <button onClick={load} className="btn-secondary inline-flex items-center gap-2 text-[13px]" data-testid="reports-refresh">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        }
      />

      {loading && !health ? (
        <BrandLoader label="Loading metrics…" />
      ) : !health ? null : (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5 mb-8">
            <Kpi label="Setups in progress" value={health.in_progress_setups} icon={Sparkles} accent="champagne" />
            <Kpi label="Completed setups" value={health.completed_setups} icon={CheckCircle2} accent="sage" />
            <Kpi label="Completion rate" value={`${health.completion_rate}%`} icon={TrendingUp} accent="ivory" />
            <Kpi label="Median time to launch" value={health.median_days_to_launch ? `${health.median_days_to_launch}d` : "—"} icon={Clock} accent="ivory" caption={health.median_days_to_launch ? `${health.median_hours_to_launch}h precise` : "No completed setups yet"} />
            <Kpi label="Invite acceptance" value={`${health.invites.acceptance_rate}%`} icon={Mail} accent="ivory" caption={`${health.invites.accepted}/${health.invites.total} accepted`} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Funnel */}
            <Card hover={false} className="lg:col-span-3">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="label-eyebrow">Step funnel</div>
                  <h3 className="font-display text-2xl text-equine-ivory mt-1">Where users complete & where they stall</h3>
                </div>
              </div>
              <Funnel funnel={health.funnel} totalSetups={Math.max(1, health.total_setups)} />
              <div className="hairline mt-5 pt-4 text-[11.5px] text-equine-platinum/60 flex gap-4 flex-wrap">
                <LegendDot tone="sage" label="Complete" />
                <LegendDot tone="champagne" label="In progress" />
                <LegendDot tone="slate" label="Skipped" />
                <LegendDot tone="graphite" label="Pending" />
              </div>
            </Card>

            {/* Nudge panel */}
            <Card hover={false} className="lg:col-span-2">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <div className="label-eyebrow">Automated outreach</div>
                  <h3 className="font-display text-2xl text-equine-ivory mt-1">Nudge stalled users</h3>
                  <p className="text-[12.5px] text-equine-platinum/60 mt-1">Auto-runs daily. Manual override below.</p>
                </div>
              </div>

              <div className="flex items-center gap-2 mb-4">
                <label className="label-eyebrow whitespace-nowrap">Stalled ≥</label>
                <input
                  type="number" min="1" max="30" value={days}
                  onChange={(e) => setDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                  data-testid="nudge-days"
                  className="w-16 bg-equine-soft border border-equine-graphite/60 rounded-lg px-2 py-1.5 text-equine-ivory text-[13px] focus:border-equine-champagne outline-none"
                />
                <span className="text-[12.5px] text-equine-platinum/70">days</span>
                <div className="flex-1" />
                <StatusPill tone="info">{candidates.length} candidate{candidates.length === 1 ? "" : "s"}</StatusPill>
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto scrollbar-luxe mb-4">
                {candidates.length === 0 && (
                  <div className="text-[13px] text-equine-platinum/60 py-4 text-center">
                    Nobody is stalled — every active setup updated within the last {days} day{days === 1 ? "" : "s"}.
                  </div>
                )}
                {candidates.map((c) => (
                  <div key={c.user_id} className="flex items-center gap-3 py-2 px-3 rounded-lg bg-equine-soft border border-equine-graphite/40" data-testid={`candidate-${c.user_id}`}>
                    <div className="w-8 h-8 rounded-full bg-equine-amber/20 border border-equine-amber/40 flex items-center justify-center text-equine-amber text-[11px] font-medium flex-shrink-0">
                      {c.days_stalled}d
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-equine-silver text-[13px] truncate">{c.full_name || c.email}</div>
                      <div className="text-[11px] text-equine-platinum/60 truncate">Next: {c.next_step_label} · {c.percent_done}% done</div>
                    </div>
                    {c.last_nudged_at && <Clock className="w-3.5 h-3.5 text-equine-platinum/40" title="Recently nudged" />}
                  </div>
                ))}
              </div>

              <button onClick={runNudges} disabled={running || candidates.length === 0} data-testid="run-nudges"
                className="btn-primary w-full inline-flex items-center justify-center gap-2 disabled:opacity-50">
                <Send className="w-4 h-4" /> {running ? "Sending…" : `Send reminder${candidates.length === 1 ? "" : "s"}`}
              </button>

              {lastRun && (
                <div className="mt-4 p-3 rounded-lg bg-equine-soft border border-equine-graphite/40" data-testid="last-run">
                  <div className="label-eyebrow mb-2">Last run</div>
                  <div className="text-[12.5px] text-equine-silver space-y-0.5">
                    <div className="flex justify-between"><span>Sent</span><span className="text-equine-sage">{lastRun.sent}</span></div>
                    <div className="flex justify-between"><span>Skipped (cooldown / sandbox)</span><span className="text-equine-platinum/70">{lastRun.skipped}</span></div>
                    {lastRun.errors > 0 && <div className="flex justify-between text-equine-clay"><span>Errors</span><span>{lastRun.errors}</span></div>}
                  </div>
                </div>
              )}

              {health.invites.acceptance_rate < 50 && health.invites.total > 0 && (
                <div className="mt-4 p-3 rounded-lg bg-equine-amber/10 border border-equine-amber/40 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-equine-amber flex-shrink-0 mt-0.5" />
                  <div className="text-[12px] text-equine-platinum/80">
                    Invite acceptance is low ({health.invites.acceptance_rate}%). Consider personalising the invitation message or verifying your sending domain in Resend.
                  </div>
                </div>
              )}
            </Card>
          </div>

          {/* Invite breakdown */}
          <Card hover={false} className="mt-6">
            <h3 className="font-display text-2xl text-equine-ivory mb-4">Invitation pipeline</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <InviteStat label="Total sent" value={health.invites.total} />
              <InviteStat label="Accepted" value={health.invites.accepted} tone="sage" />
              <InviteStat label="Pending" value={health.invites.pending} tone="champagne" />
              <InviteStat label="Revoked" value={health.invites.revoked} tone="neutral" />
              <InviteStat label="Expired" value={health.invites.expired} tone="clay" />
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

const Kpi = ({ label, value, icon: Icon, accent, caption }) => {
  const c = { sage: "text-equine-sage", champagne: "text-equine-champagne", ivory: "text-equine-ivory" }[accent] || "text-equine-ivory";
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div className="label-eyebrow">{label}</div>
        <Icon strokeWidth={1.4} className="text-equine-platinum/60 w-4 h-4" />
      </div>
      <div className={`font-display text-[40px] leading-none mt-3 ${c}`}>{value}</div>
      {caption && <div className="mt-1.5 text-[11.5px] text-equine-platinum/55">{caption}</div>}
    </Card>
  );
};

const Funnel = ({ funnel, totalSetups }) => {
  const max = Math.max(1, ...funnel.map((r) => (r.complete + r.in_progress + r.skipped + r.pending)));
  return (
    <div className="space-y-2.5">
      {funnel.map((r) => {
        const total = r.complete + r.in_progress + r.skipped + r.pending;
        const segs = [
          { v: r.complete, color: "#6E8B74" },
          { v: r.in_progress, color: "#BFC5CC" },
          { v: r.skipped, color: "#708090" },
          { v: r.pending, color: "#3A3A3A" },
        ];
        return (
          <div key={r.step} className="grid grid-cols-12 items-center gap-3" data-testid={`funnel-${r.step}`}>
            <div className="col-span-3 text-[13px] text-equine-silver truncate">{r.label}</div>
            <div className="col-span-7 h-7 rounded-md bg-equine-soft overflow-hidden flex" title={`${r.complete} complete · ${r.in_progress} in-progress · ${r.skipped} skipped · ${r.pending} pending`}>
              {segs.map((s, i) => s.v > 0 ? (
                <div key={i} style={{ width: `${(s.v / max) * 100}%`, background: s.color }} className="h-full transition-all" />
              ) : null)}
            </div>
            <div className="col-span-2 text-right text-[12.5px] text-equine-platinum/70">
              <span className="text-equine-sage">{r.complete}</span> / {total}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const LegendDot = ({ tone, label }) => {
  const c = { sage: "#6E8B74", champagne: "#BFC5CC", slate: "#708090", graphite: "#3A3A3A" }[tone];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: c }} /> {label}
    </span>
  );
};

const InviteStat = ({ label, value, tone }) => {
  const c = { sage: "text-equine-sage", champagne: "text-equine-champagne", clay: "text-equine-clay", neutral: "text-equine-platinum/70" }[tone] || "text-equine-ivory";
  return (
    <div className="p-4 rounded-xl bg-equine-soft border border-equine-graphite/40">
      <div className="label-eyebrow">{label}</div>
      <div className={`font-display text-3xl mt-1 ${c}`}>{value}</div>
    </div>
  );
};
