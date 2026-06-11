import React from "react";
import { Logo } from "./Logo";

/**
 * Phase 8C — calm branded loading state.
 * Icon-only Equine-Sync mark with a slow (~2.5s) opacity pulse + label.
 * Used sparingly on the highest-traffic loaders (Onboarding, Reports, Dashboard).
 */
export const BrandLoader = ({ label = "Loading…", tone }) => (
  <div
    className="py-16 flex flex-col items-center justify-center gap-4"
    data-testid="brand-loader"
  >
    {/* size 80: the icon-only art has ~40% transparent margin, so 80px renders a true >=48px detailed mark (Guide 22 min). */}
    <div className="animate-pulse" style={{ animationDuration: "2.5s" }}>
      <Logo variant="icon" size={80} tone={tone} />
    </div>
    <div className="text-[11px] tracking-[0.2em] uppercase text-equine-inkMuted">
      {label}
    </div>
  </div>
);
