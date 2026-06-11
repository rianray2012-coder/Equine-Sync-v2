import React, { useEffect, useMemo, useState } from "react";
import { api, fmtDate, money } from "../lib/api";
import { Card, StatusPill } from "./Primitives";
import { Wallet, ChevronDown } from "lucide-react";
import { InvoiceLineItems } from "./InvoiceLineItems";
import { InvoiceBreakdown } from "./InvoiceBreakdown";
import { normalizeInvoiceForDisplay, isPastDue, statusTone } from "../lib/invoices";

/**
 * Phase 7D-1 — owner-facing, READ-ONLY billing summary.
 *
 * The backend owner-scopes `GET /invoices` for a horse_owner (only their own
 * invoices, barn-scoped), so this component simply summarizes what it receives.
 * No payment action — purely informational.
 */
function OwnerInvoiceRow({ inv }) {
  const [open, setOpen] = useState(false);
  const d = normalizeInvoiceForDisplay(inv);
  const pastDue = isPastDue(inv);
  return (
    <div className="hairline" data-testid={`owner-invoice-${inv.id}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        data-testid={`invoice-expand-${inv.id}`}
        aria-expanded={open}
        className="w-full flex items-center gap-3 py-2.5 text-left"
      >
        <ChevronDown
          strokeWidth={1.5}
          className={`w-4 h-4 shrink-0 text-equine-inkSoft transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
        <div className="flex-1 min-w-[140px]">
          <div className="text-[13.5px] text-equine-ink">{money(d.total)}</div>
          <div className={`text-[12px] ${pastDue ? "text-equine-clay font-medium" : "text-equine-inkMuted"}`}>
            Due {inv.due_date ? fmtDate(inv.due_date) : "—"}{pastDue ? " · Past due" : ""}
          </div>
        </div>
        <StatusPill tone={statusTone(inv.status)}>{inv.status}</StatusPill>
      </button>
      {open && (
        <div className="pb-3 pl-7 pr-1" data-testid={`owner-invoice-detail-${inv.id}`}>
          <InvoiceLineItems invoiceId={inv.id} lines={d.lines} />
          <InvoiceBreakdown invoiceId={inv.id} {...d} />
        </div>
      )}
    </div>
  );
}

export default function OwnerBillingCard() {
  const [invoices, setInvoices] = useState(null);

  useEffect(() => {
    api
      .get("/invoices")
      .then((r) => setInvoices(Array.isArray(r.data) ? r.data : []))
      .catch(() => setInvoices([]));
  }, []);

  const { balance, nextDue } = useMemo(() => {
    // Explicit allow-list of "owing" statuses (the invoice model uses open/paid/overdue).
    const OWING = ["open", "overdue"];
    const open = (invoices || []).filter((i) => OWING.includes(i.status));
    const bal = open.reduce((s, i) => s + (Number(i.total) || 0), 0);
    const due = open
      .map((i) => i.due_date)
      .filter(Boolean)
      .sort()[0] || null;
    return { balance: bal, nextDue: due };
  }, [invoices]);

  return (
    <Card className="mb-8" data-testid="owner-billing-card">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-equine-soft border border-equine-hairline flex items-center justify-center">
          <Wallet strokeWidth={1.5} className="w-4 h-4 text-equine-navy" />
        </div>
        <div>
          <h2 className="font-display text-2xl text-equine-ink">Billing</h2>
          <div className="text-[12.5px] text-equine-inkMuted">Your invoices and balance with the barn.</div>
        </div>
      </div>

      {invoices === null && (
        <div className="py-8 text-center text-equine-inkSoft text-[13px]">Loading your billing…</div>
      )}

      {invoices !== null && invoices.length === 0 && (
        <div className="py-8 text-center text-equine-inkSoft text-[13px]" data-testid="owner-billing-empty">
          No invoices on file. You&apos;re all settled up.
        </div>
      )}

      {invoices !== null && invoices.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 mb-5">
            <div className="bg-equine-soft/60 border border-equine-hairline rounded-xl px-4 py-3" data-testid="owner-balance">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-equine-inkSoft mb-1">Open balance</div>
              <div className="font-display text-2xl text-equine-ink">{money(balance)}</div>
            </div>
            <div className="bg-equine-soft/60 border border-equine-hairline rounded-xl px-4 py-3" data-testid="owner-next-due">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-equine-inkSoft mb-1">Next due</div>
              <div className="font-display text-2xl text-equine-ink">{nextDue ? fmtDate(nextDue) : "—"}</div>
            </div>
          </div>

          <div className="space-y-1">
            {invoices.map((inv) => (
              <OwnerInvoiceRow key={inv.id} inv={inv} />
            ))}
          </div>
        </>
      )}
    </Card>
  );
}
