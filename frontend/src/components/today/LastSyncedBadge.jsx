import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

/**
 * LastSyncedBadge — quietly dependable, never alarming.
 *
 * Renders a small "Synced HH:mm" pill + tap-target refresh icon.
 * Used on the Today page so the groom always knows whether the data
 * in front of them is fresh — no giant connectivity warnings.
 *
 * Auto-rerenders every 30s so the relative time stays accurate
 * without re-fetching.
 */
export default function LastSyncedBadge({ at, onRefresh, refreshing = false }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  if (!at) return null;
  const now = Date.now();
  const diffSec = Math.max(0, Math.floor((now - new Date(at).getTime()) / 1000));
  let label;
  if (diffSec < 45) label = "Synced just now";
  else if (diffSec < 90) label = "Synced 1 min ago";
  else if (diffSec < 3600) label = `Synced ${Math.round(diffSec / 60)} min ago`;
  else {
    const d = new Date(at);
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    label = `Synced ${hh}:${mm}`;
  }

  return (
    <button
      type="button"
      onClick={onRefresh}
      disabled={refreshing}
      data-testid="today-last-synced"
      title="Tap to refresh"
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-equine-hairline bg-equine-card/60 text-equine-inkMuted text-[11.5px] tracking-wide hover:border-equine-graphite transition-colors tap-44"
    >
      <RefreshCw
        strokeWidth={1.6}
        className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
      />
      <span>{label}</span>
    </button>
  );
}
