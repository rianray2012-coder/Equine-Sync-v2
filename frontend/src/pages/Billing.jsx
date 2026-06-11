import React, { useEffect, useState } from "react";
import { api, fmtDate, money } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";
import { Logo } from "../components/Logo";
import { ChevronDown } from "lucide-react";
import { InvoiceLineItems } from "../components/InvoiceLineItems";
import { InvoiceBreakdown } from "../components/InvoiceBreakdown";
import { normalizeInvoiceForDisplay, isPastDue, statusTone } from "../lib/invoices";

function InvoiceRow({ inv, onPay }) {
  const [open, setOpen] = useState(false);
  const d = normalizeInvoiceForDisplay(inv);
  const pastDue = isPastDue(inv);
  const labels = d.lines.map((l) => l.label).join(", ");
  const who = inv.owner_name || inv.owner_id || "—";
  const horse = inv.horse_name || inv.horse_id;

  return (
    <div className="hairline" data-testid={`invoice-row-${inv.id}`}>
      <div className="py-4 flex items-center gap-4">
        <button
          onClick={() => setOpen((v) => !v)}
          data-testid={`invoice-expand-${inv.id}`}
          aria-expanded={open}
          className="flex-1 flex items-start gap-3 text-left min-w-0"
        >
          <ChevronDown
            strokeWidth={1.5}
            className={`w-4 h-4 mt-1 shrink-0 text-equine-inkSoft transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
          <div className="flex-1 min-w-0">
            <div className="text-equine-ink">{who}{horse ? ` · ${horse}` : ""}</div>
            <div className="text-[12.5px] text-equine-inkMuted truncate">{labels || "—"}</div>
            <div className={`text-[11.5px] mt-0.5 ${pastDue ? "text-equine-clay font-medium" : "text-equine-inkSoft"}`}>
              Due {fmtDate(inv.due_date)}{pastDue ? " · Past due" : ""}
            </div>
          </div>
        </button>
        <div className="font-display text-2xl text-equine-ink w-24 text-right shrink-0">{money(d.total)}</div>
        <StatusPill tone={statusTone(inv.status)}>{inv.status}</StatusPill>
        {inv.status !== "paid" && (
          <button
            onClick={() => onPay(inv.id)}
            data-testid={`pay-${inv.id}`}
            className="btn-secondary !py-1.5 !px-4 text-[12.5px] shrink-0"
          >
            Mark Paid
          </button>
        )}
      </div>
      {open && (
        <div className="pb-4 pl-7 pr-2" data-testid={`invoice-detail-${inv.id}`}>
          <InvoiceLineItems invoiceId={inv.id} lines={d.lines} />
          <InvoiceBreakdown invoiceId={inv.id} {...d} />
        </div>
      )}
    </div>
  );
}

export default function Billing() {
  const [invoices, setInvoices] = useState([]);
  const load = () => api.get("/invoices").then((r) => setInvoices(Array.isArray(r.data) ? r.data : []));
  useEffect(() => { load(); }, []);

  const pay = async (id) => { await api.post(`/invoices/${id}/pay`); load(); };

  const sum = (s) => invoices.filter((i) => i.status === s).reduce((a, i) => a + (Number(i.total) || 0), 0);
  const totals = { open: sum("open"), overdue: sum("overdue"), paid: sum("paid") };

  return (
    <div data-testid="billing-page">
      <div className="mb-4"><Logo size={68} /></div>
      <PageHeader eyebrow="Finance" title="Billing & Revenue" subtitle="Invoice status, overdue alerts and revenue per owner and horse." />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <Card><div className="label-eyebrow">Open</div><div className="font-display text-4xl mt-2 text-equine-champagne">{money(totals.open)}</div></Card>
        <Card><div className="label-eyebrow">Overdue</div><div className="font-display text-4xl mt-2 text-equine-clay">{money(totals.overdue)}</div></Card>
        <Card><div className="label-eyebrow">Paid (lifetime)</div><div className="font-display text-4xl mt-2 text-equine-sage">{money(totals.paid)}</div></Card>
      </div>

      <Card>
        <h2 className="font-display text-2xl mb-4">All Invoices</h2>
        {invoices.length === 0 && (
          <div className="py-8 text-center text-equine-inkSoft text-[13px]">No invoices yet.</div>
        )}
        {invoices.map((inv) => <InvoiceRow key={inv.id} inv={inv} onPay={pay} />)}
      </Card>
    </div>
  );
}
