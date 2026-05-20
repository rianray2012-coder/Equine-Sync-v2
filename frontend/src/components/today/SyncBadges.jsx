import React, { useEffect, useState } from "react";
import { subscribeSyncState, retryFailed } from "../../lib/taskSync";
import { CloudOff, RotateCw } from "lucide-react";

/** Per-task sync indicator (queued / syncing / retry / failed / synced). */
export const SyncDot = ({ state }) => {
  const map = {
    synced:  { cls: "bg-equine-sage", label: "Synced", pulse: false },
    queued:  { cls: "bg-equine-brassLight", label: "Queued", pulse: true },
    syncing: { cls: "bg-equine-brassLight", label: "Syncing", pulse: true },
    retry:   { cls: "bg-equine-amber", label: "Retrying", pulse: true },
    failed:  { cls: "bg-equine-clay", label: "Sync failed", pulse: false, ring: true },
  };
  const it = map[state] || map.synced;
  return (
    <span className="inline-flex items-center gap-1.5" title={it.label} data-testid={`sync-dot-${state}`}>
      <span className={`relative inline-flex w-1.5 h-1.5 rounded-full ${it.cls}`}>
        {it.pulse && <span className={`absolute inset-0 rounded-full ${it.cls} animate-ping opacity-50`} />}
        {it.ring && <span className="absolute -inset-1 rounded-full ring-1 ring-equine-clay/50" />}
      </span>
    </span>
  );
};

/** Header badge that surfaces aggregate queue state + manual retry. */
export const SyncHeaderBadge = () => {
  const [q, setQ] = useState([]);
  useEffect(() => subscribeSyncState(setQ), []);
  const pending = q.filter((x) => x.state === "queued" || x.state === "syncing").length;
  const failed  = q.filter((x) => x.state === "failed").length;
  if (pending === 0 && failed === 0) return null;
  return (
    <div
      data-testid="sync-header-badge"
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11.5px] tracking-wide ${
        failed > 0
          ? "bg-equine-clay/10 border-equine-clay/30 text-equine-clay"
          : "bg-equine-brass/10 border-equine-brass/30 text-equine-navy"
      }`}
    >
      {failed > 0 ? <CloudOff className="w-3.5 h-3.5" /> : <RotateCw className="w-3.5 h-3.5 animate-spin" />}
      <span>
        {failed > 0
          ? `${failed} sync issue${failed > 1 ? "s" : ""}`
          : `Syncing ${pending}…`}
      </span>
      {failed > 0 && (
        <button
          data-testid="sync-retry-now"
          onClick={() => retryFailed()}
          className="ml-1 underline underline-offset-2 hover:text-equine-ink transition-colors"
        >
          Retry now
        </button>
      )}
    </div>
  );
};
