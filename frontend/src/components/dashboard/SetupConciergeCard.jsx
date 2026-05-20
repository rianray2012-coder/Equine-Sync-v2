import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../Primitives";
import { Sparkles, ChevronRight, Check, Circle } from "lucide-react";
import { STEP_META } from "../../lib/onboardingMeta";

/**
 * SetupConciergeCard — surfaces incomplete onboarding on the dashboard.
 * Renders only when an admin/manager has progress < 100%. Each tile deep-links
 * back into /onboarding to resume the wizard at the right step.
 */
const SetupConciergeCard = ({ progress, steps }) => {
  if (!progress || progress.completed || (progress.percent ?? 0) >= 100) return null;
  if (!steps?.length) return null;

  return (
    <Card elevated hover={false} className="mb-10 animate-fade-in" data-testid="setup-checklist-card">
      <div className="flex items-start gap-4 mb-5">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-equine-brass to-equine-saddle flex items-center justify-center flex-shrink-0 shadow-lg">
          <Sparkles strokeWidth={1.4} className="text-equine-black" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="label-eyebrow">Setup concierge</div>
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <h3 className="font-display text-3xl text-equine-ivory mt-1">
              Finish setting up your barn
            </h3>
            <Link
              to="/onboarding"
              data-testid="resume-setup"
              className="btn-primary !py-2 !px-4 text-[13px] inline-flex items-center gap-2 whitespace-nowrap"
            >
              Resume <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="mt-3 flex items-center gap-4">
            <div className="flex-1 h-1.5 bg-equine-soft rounded-full overflow-hidden max-w-md">
              <div
                className="h-full bg-gradient-to-r from-equine-brass to-equine-brassLight transition-all duration-500"
                style={{ width: `${progress.percent}%` }}
              />
            </div>
            <span className="text-equine-platinum/70 text-[12.5px]">
              {progress.percent}% complete
            </span>
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
            <Link
              to="/onboarding"
              key={s.id}
              data-testid={`checklist-${s.id}`}
              className={`px-3 py-2.5 rounded-xl border transition-all duration-200 hover:border-equine-brass hover:bg-equine-elevated flex items-center gap-2.5 tap-44 ${tone}`}
            >
              {isDone
                ? <Check strokeWidth={2} className="w-4 h-4 text-equine-sage flex-shrink-0" />
                : isSkipped
                  ? <Circle strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/40 flex-shrink-0" />
                  : <Ic strokeWidth={1.5} className={`w-4 h-4 flex-shrink-0 ${isInProgress ? "text-equine-brassLight" : "text-equine-platinum/70"}`} />
              }
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] text-equine-ivory truncate">
                  {STEP_META[s.id]?.label || s.label}
                </div>
                <div className="text-[9.5px] uppercase tracking-[0.18em] text-equine-brass/65">
                  {status.replace("_", " ")}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Reassuring, non-pressuring guidance. Avoid checklist guilt. */}
      <div
        data-testid="setup-guidance"
        className="mt-5 pt-4 border-t border-equine-hairline/60 text-[12px] text-equine-platinum/65 leading-relaxed"
      >
        Many barns begin with <span className="text-equine-ivory">Horses</span> and{" "}
        <span className="text-equine-ivory">Feed Templates</span>, then expand from there.
        You can complete the remaining steps any time from Settings — nothing is locked or required to start operations.
      </div>
    </Card>
  );
};

export default SetupConciergeCard;
