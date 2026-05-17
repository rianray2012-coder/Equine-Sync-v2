import React, { useEffect, useState } from "react";
import { api, fmtDate, money } from "../lib/api";
import { Card, PageHeader, StatusPill } from "../components/Primitives";

export default function Billing() {
  const [invoices, setInvoices] = useState([]);
  const load = () => api.get("/invoices").then((r) => setInvoices(r.data));
  useEffect(() => { load(); }, []);

  const pay = async (id) => { await api.post(`/invoices/${id}/pay`); load(); };

  const totals = {
    open: invoices.filter(i => i.status === "open").reduce((a, i) => a + i.total, 0),
    overdue: invoices.filter(i => i.status === "overdue").reduce((a, i) => a + i.total, 0),
    paid: invoices.filter(i => i.status === "paid").reduce((a, i) => a + i.total, 0),
  };

  return (
    <div data-testid="billing-page">
      <PageHeader eyebrow="Finance" title="Billing & Revenue" subtitle="Invoice status, overdue alerts and revenue per owner and horse." />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <Card><div className="label-eyebrow">Open</div><div className="font-display text-4xl mt-2 text-equine-champagne">{money(totals.open)}</div></Card>
        <Card><div className="label-eyebrow">Overdue</div><div className="font-display text-4xl mt-2 text-equine-clay">{money(totals.overdue)}</div></Card>
        <Card><div className="label-eyebrow">Paid (lifetime)</div><div className="font-display text-4xl mt-2 text-equine-sage">{money(totals.paid)}</div></Card>
      </div>

      <Card>
        <h2 className="font-display text-2xl mb-4">All Invoices</h2>
        {invoices.map((i) => (
          <div key={i.id} className="py-4 hairline flex items-center gap-4">
            <div className="flex-1">
              <div className="text-equine-ivory">{i.owner_name} · {i.horse_name}</div>
              <div className="text-[12.5px] text-equine-platinum/60">{i.items.map(x => x.label).join(", ")}</div>
              <div className="text-[11.5px] text-equine-platinum/50 mt-0.5">Due {fmtDate(i.due_date)}</div>
            </div>
            <div className="font-display text-2xl text-equine-ivory w-24 text-right">{money(i.total)}</div>
            <StatusPill tone={i.status === "paid" ? "success" : i.status === "overdue" ? "critical" : "info"}>{i.status}</StatusPill>
            {i.status !== "paid" && <button onClick={() => pay(i.id)} data-testid={`pay-${i.id}`} className="btn-secondary !py-1.5 !px-4 text-[12.5px]">Mark Paid</button>}
          </div>
        ))}
      </Card>
    </div>
  );
}
