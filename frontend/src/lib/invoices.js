// Phase 9C — tolerant invoice display normalizer.
// Handles both 9A-structured invoices and legacy invoices (label-only items,
// no subtotal/discount/tax fields) without ever crashing the UI.

export const lineLabel = (li) => li?.description || li?.label || "Item";

export const normalizeInvoiceForDisplay = (inv) => {
  const items = Array.isArray(inv?.items) ? inv.items : [];
  const lines = items.map((li) => {
    const amount =
      li?.amount != null
        ? Number(li.amount)
        : li?.quantity != null && li?.unit_amount != null
        ? Number(li.quantity) * Number(li.unit_amount)
        : 0;
    return {
      label: lineLabel(li),
      quantity: li?.quantity ?? null,
      unitAmount: li?.unit_amount ?? null,
      amount: Number.isFinite(amount) ? amount : 0,
    };
  });

  const total = Number(inv?.total) || 0;
  // Legacy invoices lack the breakdown fields → fall back gracefully.
  const subtotal = inv?.subtotal != null ? Number(inv.subtotal) : total;
  const discount = inv?.discount != null ? Number(inv.discount) : 0;
  const taxRate = inv?.tax_rate != null ? Number(inv.tax_rate) : 0;
  const taxAmount = inv?.tax_amount != null ? Number(inv.tax_amount) : 0;

  return { lines, subtotal, discount, taxRate, taxAmount, total };
};

// Purely visual "past due" hint — true only for OPEN invoices whose due_date is
// before today. Never mutates status (no client-side status invention).
export const isPastDue = (inv) => {
  if (!inv || inv.status !== "open" || !inv.due_date) return false;
  const due = new Date(inv.due_date);
  if (Number.isNaN(due.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return due < today;
};

export const statusTone = (s) =>
  s === "paid" ? "success" : s === "overdue" ? "critical" : "info";
