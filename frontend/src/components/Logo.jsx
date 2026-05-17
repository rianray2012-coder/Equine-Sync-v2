import React from "react";

export const Logo = ({ size = 28, withText = true }) => (
  <div className="flex items-center gap-3" data-testid="logo">
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="EquineSync">
      <circle cx="32" cy="32" r="30" stroke="#BFC5CC" strokeWidth="1.2" />
      <path d="M20 44c0-10 6-18 14-18 4 0 7 2 9 6 1.5 3 4 3 5 1" stroke="#F5F2EC" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M22 22l4-4 3 4" stroke="#F5F2EC" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="36" cy="30" r="1.2" fill="#BFC5CC" />
    </svg>
    {withText && (
      <div className="leading-none">
        <div className="font-display text-[20px] tracking-wide text-equine-ivory">EquineSync</div>
        <div className="text-[9px] tracking-[0.32em] uppercase text-equine-platinum/60 mt-0.5">Stable Operating System</div>
      </div>
    )}
  </div>
);
