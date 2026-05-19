import React from "react";

export const Logo = ({ size = 32, withText = true }) => (
  <div className="flex items-center gap-3" data-testid="logo">
    <div className="relative">
      <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="EquineSync">
        <defs>
          <linearGradient id="brass-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#D4B884" />
            <stop offset="100%" stopColor="#8B6F4E" />
          </linearGradient>
        </defs>
        <circle cx="32" cy="32" r="29" stroke="url(#brass-ring)" strokeWidth="1.2" />
        <circle cx="32" cy="32" r="29" stroke="#332E26" strokeWidth="0.4" />
        {/* Refined monogram: stylized E + S in editorial linework */}
        <path d="M22 21h18M22 32h14M22 43h18" stroke="#F5F2EC" strokeWidth="1.2" strokeLinecap="round" />
        <path d="M40 27c-3-2-7-2-9 0s-2 5 0 6 7 1 9 3-1 6-4 6-7-1-8-3" stroke="#C9B690" strokeWidth="1.2" strokeLinecap="round" fill="none" opacity="0.85" />
      </svg>
    </div>
    {withText && (
      <div className="leading-none">
        <div className="font-display text-[21px] tracking-wide text-equine-ivory">EquineSync</div>
        <div className="text-[9px] tracking-[0.34em] uppercase text-equine-brass/70 mt-1 font-medium">Stable Operating System</div>
      </div>
    )}
  </div>
);
