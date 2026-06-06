import React, { useEffect, useMemo, useState } from "react";
import { api, fmtDate, money } from "../lib/api";
import { Card, StatusPill } from "./Primitives";
import { Wallet } from "lucide-react";

/**
 * Phase 7D-1 — owner-facing, READ-ONLY billing summary.
 *
 * The backend owner-scopes `GET /invoices` for a horse_owner (only their own
 * invoices, barn-scoped), so this component simply summarizes what it receives.
 * No payment action — purely informational.
 */
export default function OwnerBillingCard() {
  const [invoices, setInvoices] = useState(null);

  useEffect(() => {
    api
      .get("/invoices")
      .then((r) => setInvoices(Array.isArray(r.data) ? r.data : []))
      .catch(() => setInvoices([]));
  }, []);

  const { balance, nextDue } = useMemo(() => {
    const open = (invoices || []).filter((i) => i.status !== "paid");
    const bal = open.reduce((s, i) => s + (Number(i.total) || 0), 0);
    const due = open
      .map((i) => i.due_date)
      .filter(Boolean)
      .sort()[0] || null;
    return { balance: bal, nextDue: due };
  }, [invoices]);

  const toneFor = (s) =>
    s === "paid" ? "success" : s === "overdue" ? "warning" : "neutral";

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

          <div className="space-y-2">
            {invoices.map((inv) => (
              <div
                key={inv.id}
                data-testid={`owner-invoice-${inv.id}`}
                className="flex items-center gap-3 py-2.5 hairline flex-wrap"
              >
                <div className="flex-1 min-w-[160px]">
                  <div className="text-[13.5px] text-equine-ink">{money(inv.total)}</div>
                  <div className="text-[12px] text-equine-inkMuted">Due {inv.due_date ? fmtDate(inv.due_date) : "—"}</div>
                </div>
                <StatusPill tone={toneFor(inv.status)}>{inv.status}</StatusPill>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}
