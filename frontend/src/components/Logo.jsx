import React from "react";
import horseFrost from "../assets/brand/icon_horse_frost.png";
import horseDark from "../assets/brand/icon_horse_dark.png";
import horseFrostSquare from "../assets/brand/icon_horse_frost_square.png";
import horseDarkSquare from "../assets/brand/icon_horse_dark_square.png";

/**
 * Official Equine-Sync brand mark (Phase 8B).
 * Running-horse icon (frost-on-transparent for dark surfaces, graphite+lilac for light)
 * paired with a CSS-composed "Equine-Sync" wordmark — "Sync" in Smoky Lilac.
 *
 * API preserved from the previous placeholder: `size`, `withText`, `onNavy`.
 * Added (additive, optional): `variant` ('horizontal' | 'icon'), `tone` ('dark' | 'light').
 */
export const Logo = ({
  size = 36,
  withText = true,
  onNavy = false,
  variant = "horizontal",
  tone,
}) => {
  const dark = tone ? tone === "dark" : onNavy;

  // Guide 22 logo color application (logo-color correctness only; not an app-palette change)
  const equineColor = dark ? "#F7F8FA" : "#2A2A32";
  const syncColor = dark ? "#B8AECF" : "#6E5A99";
  const taglineColor = dark ? "#BCC9D6" : "#667085";

  const iconSrc = variant === "icon"
    ? (dark ? horseFrostSquare : horseDarkSquare)
    : (dark ? horseFrost : horseDark);

  const iconEl = (
    <img
      src={iconSrc}
      alt="Equine-Sync"
      style={{ height: size, width: "auto" }}
      className="object-contain shrink-0 select-none transition-opacity duration-300 group-hover/logo:opacity-80"
      draggable={false}
    />
  );

  if (variant === "icon" || !withText) {
    return (
      <span className="group/logo inline-flex items-center" data-testid="logo">
        {iconEl}
      </span>
    );
  }

  return (
    <div className="group/logo flex items-center gap-3" data-testid="logo">
      {iconEl}
      <div className="leading-none">
        <div className="font-display text-[22px] tracking-wide">
          <span style={{ color: equineColor }}>Equine-</span>
          <span style={{ color: syncColor }}>Sync</span>
        </div>
        <div
          className="text-[8.5px] tracking-[0.22em] uppercase mt-1.5 font-medium"
          style={{ color: taglineColor }}
        >
          Every Horse. Every Task. In Sync.
        </div>
      </div>
    </div>
  );
};
