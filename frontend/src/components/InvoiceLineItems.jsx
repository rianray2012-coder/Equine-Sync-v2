import React from "react";
import { money } from "../lib/api";

/**
 * Phase 9C — read-only invoice line-item table (shared by staff + owner).
 * Expects pre-normalized lines from normalizeInvoiceForDisplay().
 */
export const InvoiceLineItems = ({ invoiceId, lines }) => {
  if (!lines || lines.length === 0) {
    return (
      <div className="text-[12.5px] text-equine-inkMuted py-2" data-testid={`invoice-lines-empty-${invoiceId}`}>
        No itemized lines on this invoice.
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-equine-hairline overflow-hidden">
      <table className="w-full text-[12.5px]" data-testid={`invoice-lines-${invoiceId}`}>
        <thead>
          <tr className="bg-equine-soft/50 text-equine-inkSoft uppercase tracking-[0.14em] text-[10px]">
            <th className="text-left font-semibold px-3 py-2">Description</th>
            <th className="text-right font-semibold px-3 py-2 w-12">Qty</th>
            <th className="text-right font-semibold px-3 py-2 w-24">Unit</th>
            <th className="text-right font-semibold px-3 py-2 w-24">Amount</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((li, n) => (
            <tr
              key={n}
              data-testid={`invoice-line-${invoiceId}-${n}`}
              className="border-t border-equine-hairline"
            >
              <td className="px-3 py-2 text-equine-ink">{li.label}</td>
              <td className="px-3 py-2 text-right text-equine-inkMuted">{li.quantity ?? "—"}</td>
              <td className="px-3 py-2 text-right text-equine-inkMuted">
                {li.unitAmount != null ? money(li.unitAmount) : "—"}
              </td>
              <td className="px-3 py-2 text-right text-equine-ink">{money(li.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
