import React, { useState } from "react";
import { ChevronDown, ChevronUp, CheckSquare, Square } from "lucide-react";
import { StatusPill } from "../Primitives";
import { GROUP_META } from "../../lib/todayMeta";
import TaskCard from "./TaskCard";

/**
 * TodayGroup — one urgency-ordered band of tasks. Collapses by default
 * for non-urgent groups (later_today, completed_today, informational).
 *
 * Bulk mode: a tiny "Select all" chip appears in the header. Tap once to
 * select every visible task in this group; tap again to clear them.
 * Shaves 6–8 taps off a typical turnout round (OPERATIONAL_SIMULATION §3.1).
 */
const TodayGroup = ({
  groupKey, items, horses, onComplete, onSkip,
  onSelectToggle, selectedSet, bulkMode, syncStateForTask,
  onSelectGroup,
}) => {
  const meta = GROUP_META[groupKey];
  const [open, setOpen] = useState(!meta.collapsed);
  if (!items.length && !meta.always) return null;

  const allSelected = bulkMode
    && items.length > 0
    && items.every((t) => selectedSet.has(t.id));

  return (
    <section className="mb-7" data-testid={`group-${groupKey}`}>
      <div className="flex items-center gap-3 mb-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2.5 group"
        >
          <StatusPill tone={meta.tone} dot>{meta.label}</StatusPill>
          <span className="text-[12px] text-equine-inkMuted">{items.length}</span>
        </button>

        {bulkMode && items.length > 0 && (
          <button
            type="button"
            data-testid={`group-${groupKey}-select-all`}
            onClick={() => onSelectGroup?.(groupKey, items, !allSelected)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10.5px] uppercase tracking-[0.16em] transition-colors tap-44 ${
              allSelected
                ? "bg-equine-brassLight text-equine-navy border-equine-brass"
                : "bg-equine-card text-equine-inkMuted border-equine-hairline hover:border-equine-graphite"
            }`}
          >
            {allSelected
              ? <CheckSquare className="w-3 h-3" />
              : <Square className="w-3 h-3" />}
            {allSelected ? "All selected" : "Select all"}
          </button>
        )}

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex-1 h-px bg-equine-hairline hover:bg-equine-graphite/60 transition-colors"
          aria-label={open ? "Collapse group" : "Expand group"}
        />
        {meta.collapsed && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="text-equine-inkSoft tap-44 p-1"
            aria-label={open ? "Collapse group" : "Expand group"}
          >
            {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        )}
      </div>
      {open && (
        items.length === 0 ? (
          <div className="text-[12.5px] text-equine-inkSoft px-1 py-2 italic">
            Nothing here. A quiet stretch.
          </div>
        ) : (
          <div className="space-y-2.5">
            {items.map((t) => (
              <TaskCard
                key={t.id}
                task={t}
                horses={horses}
                onComplete={onComplete}
                onSkip={onSkip}
                onSelectToggle={onSelectToggle}
                selected={selectedSet.has(t.id)}
                bulkMode={bulkMode}
                syncStateForTask={syncStateForTask}
              />
            ))}
          </div>
        )
      )}
    </section>
  );
};

export default TodayGroup;
