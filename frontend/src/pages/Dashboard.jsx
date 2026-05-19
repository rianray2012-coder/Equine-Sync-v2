import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, money } from "../lib/api";
import { Card, PageHeader, Stat, StatusPill, SectionEyebrow } from "../components/Primitives";
import {
  Pill, AlertTriangle, BedDouble, Receipt, CloudRain, GraduationCap, ClipboardCheck,
  Stethoscope, Heart, UtensilsCrossed, Sparkles, ChevronRight, Check, Circle,
  Building2, MapPin, Users, Cat, Package, UserPlus, Calendar, Rocket, Sunrise, ArrowRight, Plus
} from "lucide-react";
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
  const navigate = useNavigate();
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
  const firstName = user?.full_name?.split(' ')[0] || "there";
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div data-testid="dashboard-page" className="pb-20 lg:pb-8">
      <PageHeader
        eyebrow={`${greeting}, ${firstName}`}
        title="Stable Command"
        subtitle="A live overview of horses, daily care, alerts and operations across your facility."
      />

      {/* ━━━━━━━━━━━━━━━━━━━━━ ONBOARDING (only when incomplete) ━━━━━━━━━━━━━━━━━━━━━ */}
      {showSetup && steps.length > 0 && (
        <Card elevated hover={false} className="mb-10 animate-fade-in" data-testid="setup-checklist-card">
          <div className="flex items-start gap-4 mb-5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-equine-brass to-equine-saddle flex items-center justify-center flex-shrink-0 shadow-lg">
              <Sparkles strokeWidth={1.4} className="text-equine-black" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="label-eyebrow">Setup concierge</div>
              <div className="flex items-end justify-between gap-4 flex-wrap">
                <h3 className="font-display text-3xl text-equine-ivory mt-1">Finish setting up your barn</h3>
                <Link to="/onboarding" data-testid="resume-setup" className="btn-primary !py-2 !px-4 text-[13px] inline-flex items-center gap-2 whitespace-nowrap">
                  Resume <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
              <div className="mt-3 flex items-center gap-4">
                <div className="flex-1 h-1.5 bg-equine-soft rounded-full overflow-hidden max-w-md">
                  <div className="h-full bg-gradient-to-r from-equine-brass to-equine-brassLight transition-all duration-500" style={{ width: `${progress.percent}%` }} />
                </div>
                <span className="text-equine-platinum/70 text-[12.5px]">{progress.percent}% complete</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {steps.map((s) => {
              const status = progress.steps?.[s.id] || "pending";
              const Ic = STEP_META[s.id]?.icon || Circle;
              const isDone = status === "complete";
              const isSkipped = status === "skipped";
              const isInProgress = status === "in_progress";
              const tone = isDone ? "border-equine-sage/40 bg-equine-sage/8"
                : isInProgress ? "border-equine-brass/40 bg-equine-brass/8"
                : isSkipped ? "border-equine-graphite/40 bg-equine-soft"
                : "border-equine-graphite/30 bg-equine-soft/60";
              return (
                <Link to="/onboarding" key={s.id} data-testid={`checklist-${s.id}`}
                  className={`px-3 py-2.5 rounded-xl border transition-all duration-200 hover:border-equine-brass hover:bg-equine-elevated flex items-center gap-2.5 tap-44 ${tone}`}
                >
                  {isDone ? <Check strokeWidth={2} className="w-4 h-4 text-equine-sage flex-shrink-0" />
                   : isSkipped ? <Circle strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/40 flex-shrink-0" />
                   : <Ic strokeWidth={1.5} className={`w-4 h-4 flex-shrink-0 ${isInProgress ? "text-equine-brassLight" : "text-equine-platinum/70"}`} />}
                  <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] text-equine-ivory truncate">{STEP_META[s.id]?.label || s.label}</div>
                    <div className="text-[9.5px] uppercase tracking-[0.18em] text-equine-brass/65">{status.replace('_', ' ')}</div>
                  </div>
                </Link>
              );
            })}
          </div>
        </Card>
      )}

      {/* ━━━━━━━━━━━━━━━━━━━━━ SECTION 1: RIGHT NOW ━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionEyebrow action={<Link to="/barn-board" className="text-[11px] uppercase tracking-[0.22em] text-equine-brass/80 hover:text-equine-brassLight inline-flex items-center gap-1.5">Open Barn Board <ArrowRight className="w-3 h-3" /></Link>}>
        Right Now · Immediate Tasks
      </SectionEyebrow>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-12 animate-fade-in">
        <ActionTile
          icon={UtensilsCrossed}
          label="Feed pending"
          value={summary?.feed_pending ?? "—"}
          caption={`of ${summary?.feed_today_total ?? 0} meals today`}
          tone="brass"
          to="/feed"
          testid="tile-feed"
        />
        <ActionTile
          icon={Pill}
          label="Medications due"
          value={summary?.meds_due ?? "—"}
          caption={summary?.meds_missed ? `${summary.meds_missed} missed earlier` : "All on schedule"}
          tone={summary?.meds_missed > 0 ? "warning" : "sage"}
          to="/medications"
          testid="tile-meds"
        />
        <ActionTile
          icon={GraduationCap}
          label="Lessons today"
          value={summary?.lessons_today ?? "—"}
          caption="Scheduled rides & lessons"
          tone="info"
          to="/lessons"
          testid="tile-lessons"
        />
        <ActionTile
          icon={BedDouble}
          label="Stall rest"
          value={summary?.stall_rest ?? "—"}
          caption={`${summary?.active_injuries ?? 0} active injuries`}
          tone={summary?.stall_rest > 0 ? "critical" : "sage"}
          to="/stall-rest"
          testid="tile-stall"
        />
      </div>

      {/* ━━━━━━━━━━━━━━━━━━━━━ SECTION 2: DAILY CARE WORKFLOWS ━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionEyebrow>Daily Care · Workflows</SectionEyebrow>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12 animate-fade-in-delay-1">
        <WeatherCard board={board} />
        <UpcomingCard summary={summary} board={board} />
        <WellnessPulseCard />
      </div>

      {/* ━━━━━━━━━━━━━━━━━━━━━ SECTION 3: ALERTS ━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionEyebrow>Attention · Alerts</SectionEyebrow>
      <Card hover={false} className="mb-12 animate-fade-in-delay-2">
        <ul className="space-y-1">
          <AlertRow icon={Pill} tone="warning" title={`${summary?.meds_due ?? 0} medications scheduled today`} desc={`${summary?.meds_missed ?? 0} missed earlier — review treatment log.`} to="/medications" />
          <AlertRow icon={BedDouble} tone="critical" title={`${summary?.stall_rest ?? 0} horses on stall rest`} desc="Cold therapy and hand-walking schedules active." to="/stall-rest" />
          <AlertRow icon={AlertTriangle} tone="warning" title={`${summary?.open_incidents ?? 0} open incidents`} desc="Owner notifications pending sign-off." to="/incidents" />
          <AlertRow icon={Receipt} tone="brass" title={`${money(summary?.overdue_amount ?? 0)} outstanding`} desc={`${summary?.overdue_invoices ?? 0} owner billing items past due.`} to="/billing" />
          <AlertRow icon={ClipboardCheck} tone="sage" title="Owner approvals pending" desc={`${summary?.pending_service_requests ?? 0} service requests awaiting decision.`} to="/owner-portal" />
        </ul>
      </Card>

      {/* ━━━━━━━━━━━━━━━━━━━━━ SECTION 4: ANALYTICS (secondary) ━━━━━━━━━━━━━━━━━━━━━ */}
      <SectionEyebrow>Operations · Analytics</SectionEyebrow>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5 animate-fade-in-delay-3">
        <Stat testid="stat-horses" label="Horses in Barn" value={summary?.total_horses ?? "—"} caption="Active in operations" icon={Cat} />
        <Stat testid="stat-wellness" label="Avg Wellness" value={summary?.avg_wellness ?? "—"} accent="sage" caption="0–100 score" icon={Heart} />
        <Stat testid="stat-meds-due" label="Meds Due" value={summary?.meds_due ?? 0} accent="amber" caption={`${summary?.meds_missed ?? 0} missed today`} icon={Pill} />
        <Stat testid="stat-injuries" label="Active Injuries" value={summary?.active_injuries ?? 0} accent="clay" caption={`${summary?.stall_rest ?? 0} on stall rest`} icon={Stethoscope} />
        <Stat testid="stat-revenue" label="Outstanding" value={money(summary?.overdue_amount ?? 0)} accent="brass" caption={`${summary?.overdue_invoices ?? 0} invoice(s)`} icon={Receipt} />
      </div>

      {/* Mobile FAB — quick jump to Barn Board */}
      <button
        onClick={() => navigate("/barn-board")}
        className="fab lg:hidden"
        data-testid="dashboard-fab"
        aria-label="Open today's barn board"
      >
        <Sunrise strokeWidth={1.6} className="w-7 h-7" />
      </button>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━ Sub-components ━━━━━━━━━━━━━━━━━━━━━

const ActionTile = ({ icon: Icon, label, value, caption, tone, to, testid }) => {
  const accent = {
    brass: { bg: "from-equine-brass/15 to-equine-saddle/5", border: "border-equine-brass/30", val: "text-equine-brassLight" },
    sage: { bg: "from-equine-sage/10 to-transparent", border: "border-equine-sage/25", val: "text-equine-sage" },
    warning: { bg: "from-equine-amber/12 to-transparent", border: "border-equine-amber/30", val: "text-equine-amber" },
    critical: { bg: "from-equine-clay/12 to-transparent", border: "border-equine-clay/30", val: "text-equine-clay" },
    info: { bg: "from-equine-brass/8 to-transparent", border: "border-equine-graphite/40", val: "text-equine-ivory" },
  }[tone];
  return (
    <Link to={to} data-testid={testid}
      className={`equine-card equine-card-hover p-5 bg-gradient-to-br ${accent.bg} ${accent.border} block group`}>
      <div className="flex items-start justify-between mb-3">
        <Icon strokeWidth={1.4} className="text-equine-brass/80 w-5 h-5" />
        <ChevronRight strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/40 group-hover:text-equine-brassLight group-hover:translate-x-0.5 transition-all" />
      </div>
      <div className="label-eyebrow mb-2">{label}</div>
      <div className={`font-display text-[44px] leading-none ${accent.val}`}>{value}</div>
      <div className="text-[12px] text-equine-platinum/60 mt-2 tracking-wide">{caption}</div>
    </Link>
  );
};

const AlertRow = ({ icon: Icon, tone, title, desc, to }) => {
  const tones = {
    warning: "text-equine-amber", clay: "text-equine-clay", sage: "text-equine-sage",
    brass: "text-equine-brassLight", critical: "text-equine-clay",
  };
  return (
    <li>
      <Link to={to || "#"} className="flex items-start gap-4 p-3 -mx-3 rounded-xl hover:bg-equine-soft/60 transition-colors">
        <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-graphite/40 flex items-center justify-center flex-shrink-0">
          <Icon strokeWidth={1.5} className={`w-5 h-5 ${tones[tone]}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-equine-ivory text-[14px]">{title}</div>
          <div className="text-equine-platinum/60 text-[12.5px] mt-0.5">{desc}</div>
        </div>
        <ChevronRight strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/40 mt-3 flex-shrink-0" />
      </Link>
    </li>
  );
};

const WeatherCard = ({ board }) => (
  <Card>
    <div className="flex items-start justify-between mb-4">
      <div>
        <div className="label-eyebrow">Weather Advisory</div>
        <h3 className="font-display text-2xl text-equine-ivory mt-1">{board?.weather?.condition || "—"}</h3>
      </div>
      <CloudRain strokeWidth={1.4} className="text-equine-brassLight" />
    </div>
    <div className="text-equine-silver/80 text-sm space-y-2">
      <div className="flex justify-between"><span>Temperature</span><span className="text-equine-ivory">{board?.weather?.temp_f ?? "—"}°F</span></div>
      <div className="py-1"><StatusPill tone="warning" dot>Caution</StatusPill></div>
      <div className="text-equine-platinum/70 text-[12.5px] leading-relaxed">{board?.weather?.alert}</div>
    </div>
  </Card>
);

const UpcomingCard = ({ summary, board }) => (
  <Card>
    <div className="flex items-start justify-between mb-4">
      <div>
        <div className="label-eyebrow">Operations</div>
        <h3 className="font-display text-2xl text-equine-ivory mt-1">Today's flow</h3>
      </div>
      <GraduationCap strokeWidth={1.4} className="text-equine-brassLight" />
    </div>
    <div className="text-equine-silver/85 text-sm">
      <div className="flex justify-between py-2.5 hairline"><span>Lessons today</span><span className="text-equine-ivory">{summary?.lessons_today ?? 0}</span></div>
      <div className="flex justify-between py-2.5 hairline"><span>Owner requests</span><span className="text-equine-amber">{summary?.pending_service_requests ?? 0}</span></div>
      <div className="flex justify-between py-2.5 hairline"><span>Feed tasks remaining</span><span className="text-equine-ivory">{summary?.feed_pending ?? 0}</span></div>
      <div className="flex justify-between py-2.5"><span>Stall rest horses</span><span className="text-equine-clay">{summary?.stall_rest ?? 0}</span></div>
    </div>
  </Card>
);

const WellnessPulseCard = () => (
  <Card>
    <div className="flex items-center justify-between mb-4">
      <div>
        <div className="label-eyebrow">Wellness</div>
        <h3 className="font-display text-2xl text-equine-ivory mt-1">Barn health pulse</h3>
      </div>
      <Heart strokeWidth={1.4} className="text-equine-brassLight" />
    </div>
    <div className="text-sm text-equine-silver/85 space-y-3">
      <PulseRow label="Normal" tone="success" pct={62} />
      <PulseRow label="Watch" tone="warning" pct={22} />
      <PulseRow label="Concern" tone="critical" pct={12} />
      <PulseRow label="Urgent" tone="critical" pct={4} />
    </div>
    <div className="mt-5 pt-4 hairline flex items-center gap-3 text-equine-platinum/65 text-[12px]">
      <Stethoscope strokeWidth={1.4} className="w-3.5 h-3.5" />
      Last barn-wide check: today, 06:40
    </div>
  </Card>
);

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
