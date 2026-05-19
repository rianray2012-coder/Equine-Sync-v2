import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, money } from "../lib/api";
import { Card, PageHeader, Stat, StatusPill } from "../components/Primitives";
import { Pill, AlertTriangle, BedDouble, Receipt, CloudRain, GraduationCap, ClipboardCheck, Stethoscope, Heart, UtensilsCrossed, Sparkles, ChevronRight, Check, Circle, Building2, MapPin, Users, Cat, Package, UserPlus, Calendar, Rocket } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const STEP_META = {
  barn: { label: "Barn Profile", icon: Building2 },
  locations: { label: "Locations", icon: MapPin },
  owners: { label: "Owners & Clients", icon: Users },
  horses: { label: "Horse Profiles", icon: Cat },
  riders: { label: "Riders", icon: GraduationCap },
  feed_templates: { label: "Feed Templates", icon: UtensilsCrossed },
  inventory: { label: "Inventory", icon: Package },
  staff: { label: "Team & Staff", icon: UserPlus },
  schedules: { label: "Recurring Schedules", icon: Calendar },
  review: { label: "Review & Launch", icon: Rocket },
};

export default function Dashboard() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [board, setBoard] = useState(null);
  const [progress, setProgress] = useState(null);
  const [steps, setSteps] = useState([]);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setSummary(r.data));
    api.get("/dashboard/barn-board").then((r) => setBoard(r.data));
    api.get("/onboarding/progress").then((r) => setProgress(r.data)).catch(() => {});
    api.get("/onboarding/steps").then((r) => setSteps(r.data.steps)).catch(() => setSteps([]));
  }, []);

  const showSetup = progress && !progress.completed && (progress.percent ?? 0) < 100;

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        eyebrow={`Welcome, ${user?.full_name?.split(' ')[0]}`}
        title="Stable Command"
        subtitle="A live overview of horses, health, operations and revenue across your facility."
      />

      {showSetup && steps.length > 0 && (
        <div className="equine-card p-6 mb-8 border-equine-steel/40" data-testid="setup-checklist-card">
          <div className="flex items-start gap-4 mb-5">
            <div className="w-12 h-12 rounded-2xl bg-equine-steel/30 border border-equine-steel/50 flex items-center justify-center flex-shrink-0">
              <Sparkles strokeWidth={1.4} className="text-equine-champagne" />
            </div>
            <div className="flex-1">
              <div className="label-eyebrow">Setup concierge</div>
              <div className="flex items-end justify-between gap-4">
                <h3 className="font-display text-3xl text-equine-ivory mt-1">Finish setting up your barn</h3>
                <Link to="/onboarding" data-testid="resume-setup" className="btn-primary !py-2 !px-4 text-[13px] inline-flex items-center gap-2 whitespace-nowrap">
                  Resume <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
              <div className="mt-3 flex items-center gap-4">
                <div className="flex-1 h-1.5 bg-equine-soft rounded-full overflow-hidden max-w-md">
                  <div className="h-full bg-equine-champagne transition-all duration-500" style={{ width: `${progress.percent}%` }} />
                </div>
                <span className="text-equine-platinum/70 text-[12.5px]">{progress.percent}% complete</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mt-2">
            {steps.map((s) => {
              const status = progress.steps?.[s.id] || "pending";
              const Ic = STEP_META[s.id]?.icon || Circle;
              const isDone = status === "complete";
              const isSkipped = status === "skipped";
              const isInProgress = status === "in_progress";
              const tone = isDone ? "border-equine-sage/40 bg-equine-sage/10"
                : isInProgress ? "border-equine-champagne/40 bg-equine-champagne/10"
                : isSkipped ? "border-equine-graphite/50 bg-equine-soft"
                : "border-equine-graphite/40 bg-equine-soft";
              return (
                <Link to="/onboarding" key={s.id} data-testid={`checklist-${s.id}`}
                  className={`px-3 py-2.5 rounded-lg border transition-colors hover:border-equine-champagne flex items-center gap-2.5 ${tone}`}
                >
                  {isDone ? (
                    <Check strokeWidth={2} className="w-4 h-4 text-equine-sage flex-shrink-0" />
                  ) : isSkipped ? (
                    <Circle strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/40 flex-shrink-0" />
                  ) : (
                    <Ic strokeWidth={1.5} className={`w-4 h-4 flex-shrink-0 ${isInProgress ? "text-equine-champagne" : "text-equine-platinum/70"}`} />
                  )}
                  <div className="min-w-0">
                    <div className="text-[12.5px] text-equine-ivory truncate">{STEP_META[s.id]?.label || s.label}</div>
                    <div className="text-[10px] uppercase tracking-[0.15em] text-equine-platinum/55">{status.replace('_', ' ')}</div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5 mb-10">
        <Stat testid="stat-horses" label="Horses in Barn" value={summary?.total_horses ?? "—"} caption="Active in operations" />
        <Stat testid="stat-wellness" label="Avg Wellness" value={summary ? `${summary.avg_wellness}` : "—"} accent="sage" caption="0–100 score" />
        <Stat testid="stat-meds-due" label="Meds Due" value={summary?.meds_due ?? 0} accent="amber" caption={`${summary?.meds_missed ?? 0} missed today`} />
        <Stat testid="stat-injuries" label="Active Injuries" value={summary?.active_injuries ?? 0} accent="clay" caption={`${summary?.stall_rest ?? 0} on stall rest`} />
        <Stat testid="stat-revenue" label="Outstanding" value={money(summary?.overdue_amount ?? 0)} accent="steel" caption={`${summary?.overdue_invoices ?? 0} invoice(s)`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Today widgets */}
        <Card>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="label-eyebrow">Today</div>
              <h3 className="font-display text-2xl text-equine-ivory mt-1">Feed Room</h3>
            </div>
            <UtensilsCrossed strokeWidth={1.4} className="text-equine-champagne" />
          </div>
          <div className="text-equine-silver/80 text-sm">
            <div className="flex justify-between py-2 hairline">
              <span>Tasks pending</span><span className="text-equine-amber font-medium">{summary?.feed_pending ?? 0}</span>
            </div>
            <div className="flex justify-between py-2 hairline">
              <span>Total meals scheduled</span><span>{summary?.feed_today_total ?? 0}</span>
            </div>
            <div className="flex justify-between py-2"><span>Soaked feeds</span><span>1 horse</span></div>
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="label-eyebrow">Operations</div>
              <h3 className="font-display text-2xl text-equine-ivory mt-1">Lessons & Rides</h3>
            </div>
            <GraduationCap strokeWidth={1.4} className="text-equine-champagne" />
          </div>
          <div className="text-equine-silver/80 text-sm">
            <div className="flex justify-between py-2 hairline"><span>Lessons today</span><span>{summary?.lessons_today ?? 0}</span></div>
            <div className="flex justify-between py-2 hairline"><span>Pending owner requests</span><span className="text-equine-amber">{summary?.pending_service_requests ?? 0}</span></div>
            <div className="flex justify-between py-2"><span>Training rides logged</span><span>4</span></div>
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="label-eyebrow">Weather Advisory</div>
              <h3 className="font-display text-2xl text-equine-ivory mt-1">{board?.weather?.condition || "—"}</h3>
            </div>
            <CloudRain strokeWidth={1.4} className="text-equine-champagne" />
          </div>
          <div className="text-equine-silver/80 text-sm">
            <div className="flex justify-between py-2 hairline"><span>Temperature</span><span>{board?.weather?.temp_f ?? "—"}°F</span></div>
            <div className="py-2"><StatusPill tone="warning">Caution</StatusPill></div>
            <div className="text-equine-platinum/70 text-[12.5px] mt-1">{board?.weather?.alert}</div>
          </div>
        </Card>

        {/* Alerts column */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="label-eyebrow">Priority</div>
              <h3 className="font-display text-2xl text-equine-ivory mt-1">Alerts requiring attention</h3>
            </div>
          </div>
          <ul className="space-y-3">
            <AlertRow icon={Pill} tone="amber" title={`${summary?.meds_due ?? 0} medications scheduled today`} desc={`${summary?.meds_missed ?? 0} missed earlier — review treatment log.`} />
            <AlertRow icon={BedDouble} tone="clay" title={`${summary?.stall_rest ?? 0} horses on stall rest`} desc="Cold therapy and hand-walking schedules active." />
            <AlertRow icon={AlertTriangle} tone="amber" title={`${summary?.open_incidents ?? 0} open incidents`} desc="Owner notifications pending sign-off." />
            <AlertRow icon={Receipt} tone="steel" title={`${money(summary?.overdue_amount ?? 0)} outstanding invoices`} desc={`${summary?.overdue_invoices ?? 0} owner billing items past due.`} />
            <AlertRow icon={ClipboardCheck} tone="sage" title="Owner approvals pending" desc={`${summary?.pending_service_requests ?? 0} service requests awaiting decision.`} />
          </ul>
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="label-eyebrow">Wellness</div>
              <h3 className="font-display text-2xl text-equine-ivory mt-1">Horse health pulse</h3>
            </div>
            <Heart strokeWidth={1.4} className="text-equine-champagne" />
          </div>
          <div className="text-sm text-equine-silver/80 space-y-3">
            <PulseRow label="Normal" tone="success" pct={62} />
            <PulseRow label="Watch" tone="warning" pct={22} />
            <PulseRow label="Concern" tone="critical" pct={12} />
            <PulseRow label="Urgent" tone="critical" pct={4} />
          </div>
          <div className="mt-5 pt-4 hairline flex items-center gap-3 text-equine-platinum/70 text-[12.5px]">
            <Stethoscope strokeWidth={1.4} className="w-4 h-4" />
            Last barn-wide check: today, 06:40
          </div>
        </Card>
      </div>
    </div>
  );
}

const AlertRow = ({ icon: Icon, tone, title, desc }) => {
  const tones = { amber: "text-equine-amber", clay: "text-equine-clay", sage: "text-equine-sage", steel: "text-equine-champagne" };
  return (
    <li className="flex items-start gap-4 p-3 -mx-3 rounded-xl hover:bg-equine-soft/60 transition-colors">
      <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-graphite/40 flex items-center justify-center">
        <Icon strokeWidth={1.5} className={`w-5 h-5 ${tones[tone]}`} />
      </div>
      <div className="flex-1">
        <div className="text-equine-ivory text-[14px]">{title}</div>
        <div className="text-equine-platinum/60 text-[12.5px] mt-0.5">{desc}</div>
      </div>
    </li>
  );
};

const PulseRow = ({ label, tone, pct }) => {
  const bar = { success: "bg-equine-sage", warning: "bg-equine-amber", critical: "bg-equine-clay" }[tone];
  return (
    <div>
      <div className="flex justify-between mb-1.5"><span>{label}</span><span className="text-equine-platinum/70">{pct}%</span></div>
      <div className="h-1.5 bg-equine-soft rounded-full overflow-hidden">
        <div className={`h-full ${bar}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};
