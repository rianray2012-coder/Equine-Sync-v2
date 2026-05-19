import React from "react";

export const Logo = ({ size = 32, withText = true, onNavy = false }) => {
  const ring = onNavy ? "#C2CDEC" : "#2E3448";
  const accent = onNavy ? "#A7B7E7" : "#A593C0";
  const ink = onNavy ? "#F7F5FA" : "#2E3448";
  const eyebrow = onNavy ? "#A7B7E7" : "#666674";
  return (
    <div className="flex items-center gap-3" data-testid="logo">
      <div className="relative">
        <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="EquineSync">
          <defs>
            <linearGradient id={`metal-ring-${onNavy ? 'd' : 'l'}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor={ring} stopOpacity="0.95" />
              <stop offset="100%" stopColor={accent} stopOpacity="0.85" />
            </linearGradient>
          </defs>
          <circle cx="32" cy="32" r="29" stroke={`url(#metal-ring-${onNavy ? 'd' : 'l'})`} strokeWidth="1.2" />
          <path d="M22 21h18M22 32h14M22 43h18" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
          <path d="M40 27c-3-2-7-2-9 0s-2 5 0 6 7 1 9 3-1 6-4 6-7-1-8-3" stroke={accent} strokeWidth="1.2" strokeLinecap="round" fill="none" opacity="0.9" />
        </svg>
      </div>
      {withText && (
        <div className="leading-none">
          <div className="font-display text-[21px] tracking-wide" style={{ color: ink }}>EquineSync</div>
          <div className="text-[9px] tracking-[0.34em] uppercase mt-1 font-medium" style={{ color: eyebrow }}>Stable Operating System</div>
        </div>
      )}
    </div>
  );
};
