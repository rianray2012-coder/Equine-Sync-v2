import React from "react";
import { money } from "../lib/api";

const Row = ({ label, value, muted }) => (
  <div className="flex items-center justify-between">
    <span className={muted ? "text-equine-inkMuted" : "text-equine-ink"}>{label}</span>
    <span className={muted ? "text-equine-inkMuted" : "text-equine-ink"}>{value}</span>
  </div>
);

/**
 * Phase 9C — invoice money breakdown (shared by staff + owner).
 * Discount/Tax rows hidden when 0 so legacy invoices collapse to just a Total.
 */
export const InvoiceBreakdown = ({ invoiceId, subtotal, discount, taxRate, taxAmount, total }) => (
  <div className="mt-3 space-y-1.5 text-[13px]" data-testid={`invoice-breakdown-${invoiceId}`}>
    <Row label="Subtotal" value={money(subtotal)} />
    {discount > 0 && <Row label="Discount" value={`− ${money(discount)}`} muted />}
    {taxAmount > 0 && (
      <Row label={`Tax${taxRate ? ` (${taxRate}%)` : ""}`} value={money(taxAmount)} muted />
    )}
    <div className="flex items-center justify-between pt-1.5 border-t border-equine-hairline">
      <span className="font-semibold text-equine-ink">Total</span>
      <span className="font-display text-lg text-equine-ink" data-testid={`invoice-total-${invoiceId}`}>
        {money(total)}
      </span>
    </div>
  </div>
);
