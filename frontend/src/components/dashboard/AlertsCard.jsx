import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../Primitives";
import {
  Pill, BedDouble, AlertTriangle, Receipt, ClipboardCheck, ChevronRight,
} from "lucide-react";
import { money } from "../../lib/api";

const TONES = {
  warning:  "text-equine-amber",
  clay:     "text-equine-clay",
  sage:     "text-equine-sage",
  brass:    "text-equine-brassLight",
  critical: "text-equine-clay",
};

const AlertRow = ({ icon: Icon, tone, title, desc, to, testid }) => (
  <li>
    <Link
      to={to || "#"}
      data-testid={testid}
      className="flex items-start gap-4 p-3 -mx-3 rounded-xl hover:bg-equine-soft/60 transition-colors"
    >
      <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-graphite/40 flex items-center justify-center flex-shrink-0">
        <Icon strokeWidth={1.5} className={`w-5 h-5 ${TONES[tone]}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-equine-ivory text-[14px]">{title}</div>
        <div className="text-equine-platinum/60 text-[12.5px] mt-0.5">{desc}</div>
      </div>
      <ChevronRight strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/40 mt-3 flex-shrink-0" />
    </Link>
  </li>
);

const AlertsCard = ({ summary }) => (
  <Card hover={false} className="mb-12 animate-fade-in-delay-2" data-testid="alerts-card">
    <ul className="space-y-1">
      <AlertRow
        testid="alert-meds"
        icon={Pill}
        tone="warning"
        title={`${summary?.meds_due ?? 0} medications scheduled today`}
        desc={`${summary?.meds_missed ?? 0} missed earlier — review treatment log.`}
        to="/medications"
      />
      <AlertRow
        testid="alert-stall-rest"
        icon={BedDouble}
        tone="critical"
        title={`${summary?.stall_rest ?? 0} horses on stall rest`}
        desc="Cold therapy and hand-walking schedules active."
        to="/stall-rest"
      />
      <AlertRow
        testid="alert-incidents"
        icon={AlertTriangle}
        tone="warning"
        title={`${summary?.open_incidents ?? 0} open incidents`}
        desc="Owner notifications pending sign-off."
        to="/incidents"
      />
      <AlertRow
        testid="alert-billing"
        icon={Receipt}
        tone="brass"
        title={`${money(summary?.overdue_amount ?? 0)} outstanding`}
        desc={`${summary?.overdue_invoices ?? 0} owner billing items past due.`}
        to="/billing"
      />
      <AlertRow
        testid="alert-owner-approvals"
        icon={ClipboardCheck}
        tone="sage"
        title="Owner approvals pending"
        desc={`${summary?.pending_service_requests ?? 0} service requests awaiting decision.`}
        to="/owner-portal"
      />
    </ul>
  </Card>
);

export default AlertsCard;
