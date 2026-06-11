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
    <div className="animate-pulse" style={{ animationDuration: "2.5s" }}>
      <Logo variant="icon" size={44} tone={tone} />
    </div>
    <div className="text-[11px] tracking-[0.2em] uppercase text-equine-inkMuted">
      {label}
    </div>
  </div>
);
