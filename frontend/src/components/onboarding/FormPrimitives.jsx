import React from "react";
import {
  Select as ShadSelect, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from "../ui/select";

/** Plain text input with eyebrow label. Used by every onboarding step. */
export const Field = ({ label, value, onChange, placeholder, type = "text", testid }) => (
  <label className="block">
    <div className="label-eyebrow mb-1.5">{label}</div>
    <input
      type={type}
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      data-testid={testid}
      className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory focus:border-equine-champagne outline-none text-[14px] transition-colors"
    />
  </label>
);

/** Shadcn-backed select with the same eyebrow shell. */
export const Select = ({ label, value, onChange, options, testid }) => (
  <label className="block">
    <div className="label-eyebrow mb-1.5">{label}</div>
    <ShadSelect value={value || ""} onValueChange={(v) => onChange(v)}>
      <SelectTrigger
        data-testid={testid}
        className="w-full bg-equine-soft border border-equine-graphite/60 rounded-lg px-3 py-2.5 text-equine-ivory hover:border-equine-graphite focus:border-equine-champagne text-[14px] h-auto"
      >
        <SelectValue placeholder="Choose…" />
      </SelectTrigger>
      <SelectContent className="bg-equine-card border-equine-graphite/60 text-equine-ivory">
        {options.map((o) => (
          <SelectItem
            key={o.v}
            value={o.v}
            className="capitalize focus:bg-equine-soft focus:text-equine-ivory"
          >
            {o.l}
          </SelectItem>
        ))}
      </SelectContent>
    </ShadSelect>
  </label>
);
