import React from "react";
import { Info } from "lucide-react";

/**
 * SoftWarning — calm informational note, NEVER blocking.
 *
 * Used for scheduling-conflict awareness (Batch D) and similar
 * "we noticed something, you might want to check" surfaces.
 * Distinct from the amber error banner — soft slate background,
 * no severity colour, supportive tone.
 */
export default function SoftWarning({ children, testid }) {
  return (
    <div
      data-testid={testid}
      className="flex items-start gap-2.5 px-3.5 py-2.5 rounded-lg bg-equine-soft/40 border border-equine-graphite/40 text-equine-silver text-[12.5px] leading-relaxed"
    >
      <Info strokeWidth={1.6} className="w-4 h-4 mt-px shrink-0 text-equine-platinum/60" />
      <span>{children}</span>
    </div>
  );
}
