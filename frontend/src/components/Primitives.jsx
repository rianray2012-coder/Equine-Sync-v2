import React from "react";

export const PageHeader = ({ eyebrow, title, subtitle, action }) => (
  <div className="flex items-end justify-between mb-10 gap-4 flex-wrap">
    <div className="max-w-2xl">
      {eyebrow && <div className="label-eyebrow mb-3">{eyebrow}</div>}
      <h1 className="font-display text-4xl sm:text-5xl lg:text-[56px] text-equine-ivory leading-[1.05]">{title}</h1>
      {subtitle && <p className="mt-4 text-equine-inkMuted text-[15.5px] leading-relaxed">{subtitle}</p>}
    </div>
    {action}
  </div>
);

export const SectionEyebrow = ({ children, action }) => (
  <div className="section-eyebrow">
    <div className="label-eyebrow whitespace-nowrap">{children}</div>
    <div className="line" />
    {action}
  </div>
);

export const Card = ({ children, className = "", hover = true, elevated = false, ...rest }) => (
  <div className={`${elevated ? "equine-card-elevated" : "equine-card"} ${hover && !elevated ? "equine-card-hover" : ""} p-6 ${className}`} {...rest}>
    {children}
  </div>
);

export const Stat = ({ label, value, accent = "ivory", caption, testid, icon: Icon }) => {
  const colors = {
    ivory: "text-equine-ivory",
    sage: "text-equine-sage",
    amber: "text-equine-amber",
    clay: "text-equine-clay",
    brass: "text-equine-brassLight",
    steel: "text-equine-champagne",
  };
  return (
    <Card data-testid={testid}>
      <div className="flex items-start justify-between mb-3">
        <div className="label-eyebrow">{label}</div>
        {Icon && <Icon strokeWidth={1.4} className="text-equine-brass/60 w-4 h-4" />}
      </div>
      <div className={`font-display text-[44px] leading-none ${colors[accent]}`}>{value}</div>
      {caption && <div className="mt-2.5 text-[11.5px] text-equine-platinum/55 tracking-wide">{caption}</div>}
    </Card>
  );
};

export const StatusPill = ({ tone = "info", children, dot = false }) => {
  const map = {
    success: "bg-equine-sage/12 text-equine-sage border-equine-sage/30",
    warning: "bg-equine-amber/12 text-equine-amber border-equine-amber/30",
    critical: "bg-equine-clay/12 text-equine-clay border-equine-clay/30",
    info: "bg-equine-brass/12 text-equine-brassLight border-equine-brass/30",
    brass: "bg-equine-brass/12 text-equine-brassLight border-equine-brass/35",
    saddle: "bg-equine-saddle/12 text-equine-champagne border-equine-saddle/35",
    neutral: "bg-equine-soft text-equine-platinum/85 border-equine-graphite/40",
  };
  const dotColor = {
    success: "bg-equine-sage", warning: "bg-equine-amber", critical: "bg-equine-clay",
    info: "bg-equine-brassLight", brass: "bg-equine-brassLight", saddle: "bg-equine-saddle", neutral: "bg-equine-platinum/50",
  }[tone];
  return (
    <span className={`pill ${map[tone]}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${dotColor}`} />}
      {children}
    </span>
  );
};

export const Empty = ({ children }) => (
  <Card hover={false} className="text-center py-14 text-equine-platinum/60">{children}</Card>
);
