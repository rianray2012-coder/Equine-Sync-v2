import React from "react";

export const PageHeader = ({ eyebrow, title, subtitle, action }) => (
  <div className="flex items-end justify-between mb-8 gap-4 flex-wrap">
    <div>
      {eyebrow && <div className="label-eyebrow mb-3">{eyebrow}</div>}
      <h1 className="font-display text-4xl sm:text-5xl text-equine-ivory leading-none">{title}</h1>
      {subtitle && <p className="mt-3 text-equine-silver/70 text-[15px] max-w-2xl">{subtitle}</p>}
    </div>
    {action}
  </div>
);

export const Card = ({ children, className = "", hover = true, ...rest }) => (
  <div className={`equine-card ${hover ? "equine-card-hover" : ""} p-6 ${className}`} {...rest}>
    {children}
  </div>
);

export const Stat = ({ label, value, accent = "ivory", caption, testid }) => {
  const colors = {
    ivory: "text-equine-ivory",
    sage: "text-equine-sage",
    amber: "text-equine-amber",
    clay: "text-equine-clay",
    steel: "text-equine-champagne",
  };
  return (
    <Card data-testid={testid}>
      <div className="label-eyebrow">{label}</div>
      <div className={`font-display text-[42px] leading-none mt-3 ${colors[accent]}`}>{value}</div>
      {caption && <div className="mt-2 text-[12px] text-equine-platinum/60">{caption}</div>}
    </Card>
  );
};

export const StatusPill = ({ tone = "info", children }) => {
  const map = {
    success: "bg-equine-sage/15 text-equine-sage border-equine-sage/30",
    warning: "bg-equine-amber/15 text-equine-amber border-equine-amber/30",
    critical: "bg-equine-clay/15 text-equine-clay border-equine-clay/30",
    info: "bg-equine-steel/20 text-equine-champagne border-equine-steel/40",
    neutral: "bg-equine-soft text-equine-platinum border-equine-graphite/50",
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[10.5px] tracking-[0.16em] uppercase border ${map[tone]}`}>
      {children}
    </span>
  );
};

export const Empty = ({ children }) => (
  <Card hover={false} className="text-center py-14 text-equine-platinum/60">{children}</Card>
);
