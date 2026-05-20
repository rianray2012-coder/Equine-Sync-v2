import React from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

/**
 * ActionTile — single high-density urgency tile for the "Right Now" row.
 * Tone-driven gradient + accent. Keep these visually loud but operationally
 * calm — they're a glance, not a dashboard.
 */
const ACCENT = {
  brass:    { bg: "from-equine-brass/15 to-equine-saddle/5",  border: "border-equine-brass/30",      val: "text-equine-brassLight" },
  sage:     { bg: "from-equine-sage/10 to-transparent",       border: "border-equine-sage/25",       val: "text-equine-sage" },
  warning:  { bg: "from-equine-amber/12 to-transparent",      border: "border-equine-amber/30",      val: "text-equine-amber" },
  critical: { bg: "from-equine-clay/12 to-transparent",       border: "border-equine-clay/30",       val: "text-equine-clay" },
  info:     { bg: "from-equine-brass/8 to-transparent",       border: "border-equine-graphite/40",   val: "text-equine-ivory" },
};

const ActionTile = ({ icon: Icon, label, value, caption, tone, to, testid }) => {
  const a = ACCENT[tone] || ACCENT.info;
  return (
    <Link
      to={to}
      data-testid={testid}
      className={`equine-card equine-card-hover p-5 bg-gradient-to-br ${a.bg} ${a.border} block group`}
    >
      <div className="flex items-start justify-between mb-3">
        <Icon strokeWidth={1.4} className="text-equine-brass/80 w-5 h-5" />
        <ChevronRight
          strokeWidth={1.5}
          className="w-4 h-4 text-equine-platinum/40 group-hover:text-equine-brassLight group-hover:translate-x-0.5 transition-all"
        />
      </div>
      <div className="label-eyebrow mb-2">{label}</div>
      <div className={`font-display text-[44px] leading-none ${a.val}`}>{value}</div>
      <div className="text-[12px] text-equine-platinum/60 mt-2 tracking-wide">{caption}</div>
    </Link>
  );
};

export default ActionTile;
