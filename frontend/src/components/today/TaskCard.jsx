import React, { useRef, useState } from "react";
import { Check, X, AlertTriangle, Clock, CheckCircle2 } from "lucide-react";
import { fmtTime } from "../../lib/api";
import { CATEGORY_META } from "../../lib/todayMeta";
import { SyncDot } from "./SyncBadges";

/**
 * TaskCard — swipe right/left on touch, button on desktop. Bulk-select
 * mode swaps the icon for a checkbox. Preserves operational urgency
 * with the Critical badge and the one-thumb 44px tap target.
 */
const TaskCard = ({
  task, horses, onComplete, onSkip, onSelectToggle,
  selected, bulkMode, syncStateForTask,
}) => {
  const meta = CATEGORY_META[task.category] || CATEGORY_META.custom;
  const Icon = meta.icon;
  const horseNames = (task.linked_horse_ids || []).map((id) => horses[id]?.name).filter(Boolean);
  const horsesLabel = horseNames.length === 0 ? "All horses"
    : horseNames.length <= 2 ? horseNames.join(" · ")
    : `${horseNames.slice(0, 2).join(" · ")} +${horseNames.length - 2}`;

  const [dx, setDx] = useState(0);
  const startRef = useRef({ x: 0, t: 0, active: false });
  const completed = task.status === "completed" || task.status === "skipped";

  const onTouchStart = (e) => {
    if (completed || bulkMode) return;
    const t = e.touches[0];
    startRef.current = { x: t.clientX, t: Date.now(), active: true };
  };
  const onTouchMove = (e) => {
    if (!startRef.current.active) return;
    const t = e.touches[0];
    const delta = t.clientX - startRef.current.x;
    setDx(Math.max(-100, Math.min(160, delta)));
  };
  const onTouchEnd = () => {
    if (!startRef.current.active) return;
    startRef.current.active = false;
    if (dx > 90) {
      setDx(180);
      setTimeout(() => { setDx(0); onComplete(task); }, 180);
    } else if (dx < -70) {
      setDx(-120);
      setTimeout(() => { setDx(0); onSkip(task); }, 180);
    } else {
      setDx(0);
    }
  };

  const swipeOpacity = Math.min(1, Math.abs(dx) / 90);
  const sync = syncStateForTask(task.id);

  return (
    <div className="relative" data-testid={`task-row-${task.id}`}>
      {dx > 4 && (
        <div className="absolute inset-y-0 left-0 right-0 rounded-2xl bg-equine-sage/15 flex items-center pl-5 pointer-events-none"
             style={{ opacity: swipeOpacity }}>
          <Check strokeWidth={2} className="w-5 h-5 text-equine-sage" />
          <span className="ml-2 text-[12px] text-equine-sage font-medium tracking-wide">Complete</span>
        </div>
      )}
      {dx < -4 && (
        <div className="absolute inset-y-0 left-0 right-0 rounded-2xl bg-equine-clay/15 flex items-center justify-end pr-5 pointer-events-none"
             style={{ opacity: swipeOpacity }}>
          <span className="mr-2 text-[12px] text-equine-clay font-medium tracking-wide">Skip</span>
          <X strokeWidth={2} className="w-5 h-5 text-equine-clay" />
        </div>
      )}

      <div
        className={`relative bg-equine-card border border-equine-hairline rounded-2xl px-4 py-3.5 transition-transform duration-150 ease-out
          ${completed ? "opacity-60" : ""}
          ${selected ? "ring-2 ring-equine-brassLight" : ""}`}
        style={{ transform: `translateX(${dx}px)` }}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <div className="flex items-center gap-3.5">
          {bulkMode ? (
            <button
              onClick={() => onSelectToggle(task.id)}
              data-testid={`bulk-toggle-${task.id}`}
              className={`flex-shrink-0 w-6 h-6 rounded-md border-2 flex items-center justify-center transition-colors
                ${selected ? "bg-equine-navy border-equine-navy text-white" : "border-equine-graphite hover:border-equine-navy"}`}
              aria-label={selected ? "Deselect" : "Select"}
            >
              {selected && <Check className="w-3.5 h-3.5" strokeWidth={3} />}
            </button>
          ) : (
            <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center flex-shrink-0">
              <Icon strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <div className="text-[14px] text-equine-ink font-medium truncate">{task.title}</div>
              {task.priority === "critical" && (
                <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.18em] text-equine-clay font-semibold">
                  <AlertTriangle className="w-3 h-3" /> Critical
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-[12px] text-equine-inkMuted flex-wrap">
              <Clock className="w-3 h-3" />
              <span>{fmtTime(task.scheduled_at)}</span>
              <span className="text-equine-inkSoft">·</span>
              <span className="truncate">{horsesLabel}</span>
              {task.assignee_role && (
                <>
                  <span className="text-equine-inkSoft">·</span>
                  <span className="capitalize">{task.assignee_role.replace(/_/g, " ")}</span>
                </>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            {sync && <SyncDot state={sync} />}
            {completed ? (
              <CheckCircle2 className="w-5 h-5 text-equine-sage" />
            ) : !bulkMode ? (
              <>
                <button
                  onClick={() => onSkip(task)}
                  data-testid={`skip-btn-${task.id}`}
                  className="hidden sm:inline-flex items-center justify-center w-9 h-9 rounded-xl text-equine-clay hover:bg-equine-clay/10 transition-colors"
                  aria-label="Skip task"
                >
                  <X className="w-4 h-4" strokeWidth={2} />
                </button>
                <button
                  onClick={() => onComplete(task)}
                  data-testid={`complete-btn-${task.id}`}
                  className="inline-flex items-center justify-center w-11 h-11 rounded-xl bg-equine-navy text-white shadow-sm hover:bg-equine-navyLift active:scale-95 transition-all"
                  aria-label="Complete task"
                >
                  <Check className="w-5 h-5" strokeWidth={2.2} />
                </button>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskCard;
