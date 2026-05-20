import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { StatusPill } from "../Primitives";
import { GROUP_META } from "../../lib/todayMeta";
import TaskCard from "./TaskCard";

/**
 * TodayGroup — one urgency-ordered band of tasks. Collapses by default
 * for non-urgent groups (later_today, completed_today, informational).
 */
const TodayGroup = ({
  groupKey, items, horses, onComplete, onSkip,
  onSelectToggle, selectedSet, bulkMode, syncStateForTask,
}) => {
  const meta = GROUP_META[groupKey];
  const [open, setOpen] = useState(!meta.collapsed);
  if (!items.length && !meta.always) return null;
  return (
    <section className="mb-7" data-testid={`group-${groupKey}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 mb-3 group"
      >
        <div className="flex items-center gap-2.5">
          <StatusPill tone={meta.tone} dot>{meta.label}</StatusPill>
          <span className="text-[12px] text-equine-inkMuted">{items.length}</span>
        </div>
        <div className="flex-1 h-px bg-equine-hairline group-hover:bg-equine-graphite/60 transition-colors" />
        {meta.collapsed && (open
          ? <ChevronUp className="w-4 h-4 text-equine-inkSoft" />
          : <ChevronDown className="w-4 h-4 text-equine-inkSoft" />
        )}
      </button>
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
