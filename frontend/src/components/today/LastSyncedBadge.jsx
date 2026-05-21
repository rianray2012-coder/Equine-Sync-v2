import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

/**
 * LastSyncedBadge — quietly dependable, never alarming.
 *
 * Used on /today and /dashboard so the operator always knows whether the data
 * in front of them is fresh. Strictly informational. No connectivity-state
 * dramatization, no warning colours.
 *
 * Props:
 *   at         Date|string when the data was last refreshed (null hides the badge).
 *   onRefresh  Callback for tap-to-refresh.
 *   refreshing Whether a refresh is currently in flight (spins the icon).
 *   verb       "Synced" (default, used on /today) or "Updated" (used on /dashboard).
 *   tone       "primary" (default) or "secondary" (smaller, borderless — for Dashboard).
 */
export default function LastSyncedBadge({
  at,
  onRefresh,
  refreshing = false,
  verb = "Synced",
  tone = "primary",
}) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  if (!at) return null;
  const now = Date.now();
  const diffSec = Math.max(0, Math.floor((now - new Date(at).getTime()) / 1000));
  let label;
  if (diffSec < 45) label = `${verb} just now`;
  else if (diffSec < 90) label = `${verb} 1 min ago`;
  else if (diffSec < 3600) label = `${verb} ${Math.round(diffSec / 60)}m ago`;
  else {
    const d = new Date(at);
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    label = `${verb} ${hh}:${mm}`;
  }

  const secondary = tone === "secondary";
  const cls = secondary
    ? "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10.5px] uppercase tracking-[0.18em] text-equine-platinum/50 hover:text-equine-platinum/80 transition-colors"
    : "inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-equine-hairline bg-equine-card/60 text-equine-inkMuted text-[11.5px] tracking-wide hover:border-equine-graphite transition-colors tap-44";

  return (
    <button
      type="button"
      onClick={onRefresh}
      disabled={refreshing}
      data-testid={secondary ? "dashboard-last-synced" : "today-last-synced"}
      title="Tap to refresh"
      className={cls}
    >
      <RefreshCw
        strokeWidth={1.6}
        className={`${secondary ? "w-3 h-3" : "w-3.5 h-3.5"} ${refreshing ? "animate-spin" : ""}`}
      />
      <span>{label}</span>
    </button>
  );
}
