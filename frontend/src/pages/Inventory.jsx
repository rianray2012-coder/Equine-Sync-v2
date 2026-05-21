import React, { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, AlertTriangle, Package } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { Card, PageHeader, StatusPill, Empty } from "../components/Primitives";
import QuickAddSheet from "../components/QuickAddSheet";
import SoftWarning from "../components/SoftWarning";

const CATEGORIES = ["grain", "hay", "bedding", "supplements", "medical", "blankets", "tack", "other"];

const ADD_FIELDS = [
  { key: "category", label: "Category", kind: "select", opts: CATEGORIES, required: true },
  { key: "name", label: "Item", placeholder: "Triple Crown Senior", required: true, full: true },
  { key: "quantity", label: "On hand", type: "number", placeholder: "120" },
  { key: "unit", label: "Unit", placeholder: "lbs / bales / count" },
  { key: "reorder_at", label: "Reorder at", type: "number", placeholder: "40" },
  { key: "vendor", label: "Vendor", placeholder: "Tractor Supply" },
  { key: "cost_per_unit", label: "Cost / unit", type: "number" },
  { key: "notes", label: "Notes", kind: "textarea", full: true, placeholder: "Stored in the feed-room loft." },
];

export default function Inventory() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/inventory");
      setItems(r.data);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const remove = async (id) => {
    try {
      await api.delete(`/inventory/${id}`);
      toast.success("Removed");
      load();
    } catch {
      toast.error("Could not remove");
    }
  };

  // Group by category for calm scanability.
  const byCategory = items.reduce((acc, it) => {
    const k = it.category || "other";
    (acc[k] = acc[k] || []).push(it);
    return acc;
  }, {});

  const lowStockCount = items.filter((i) => i.low_stock).length;

  // Soft duplicate-detection: a similar name + same category already exists.
  // Informational only — never blocks the add. Helps prevent the
  // "I forgot we already had timothy in another row" fragmentation
  // surfaced in OPERATIONAL_SIMULATION §3.4.
  const renderWarnings = useCallback((form) => {
    if (!form?.name || !form?.category) return null;
    const target = form.name.trim().toLowerCase();
    if (!target) return null;
    const dupe = items.find(
      (i) => i.category === form.category
             && (i.name || "").trim().toLowerCase() === target,
    );
    if (!dupe) return null;
    return (
      <SoftWarning testid="inventory-add-duplicate">
        {`A similar inventory item ("${dupe.name}") already exists in ${form.category}. You can still add this one — or close and edit the existing row instead.`}
      </SoftWarning>
    );
  }, [items]);

  return (
    <div data-testid="inventory-page">
      <PageHeader
        eyebrow="Operations"
        title="Inventory"
        subtitle="Grain, hay, bedding, supplements and medical supplies. Reorder thresholds flag low stock automatically."
        action={
          <div className="flex items-center gap-3">
            {lowStockCount > 0 && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-2 rounded-full bg-equine-amber/12 border border-equine-amber/30 text-equine-amber text-[12px]" data-testid="inventory-low-stock-badge">
                <AlertTriangle className="w-3.5 h-3.5" />
                {lowStockCount} low stock
              </div>
            )}
            <button
              onClick={() => setAddOpen(true)}
              data-testid="inventory-add-btn"
              className="btn-primary inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" /> Add item
            </button>
          </div>
        }
      />

      {loading ? (
        <div className="text-equine-platinum/60 text-sm">Loading inventory…</div>
      ) : items.length === 0 ? (
        <Empty>
          <Package strokeWidth={1.4} className="w-7 h-7 mx-auto mb-3 text-equine-champagne" />
          <div className="font-display text-2xl text-equine-ivory mb-1">No inventory yet</div>
          <div className="text-[13px] text-equine-platinum/60 mb-4">Add your first item to start tracking stock + reorder alerts.</div>
          <button onClick={() => setAddOpen(true)} data-testid="inventory-empty-add" className="btn-primary inline-flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add first item
          </button>
        </Empty>
      ) : (
        <div className="space-y-5">
          {Object.entries(byCategory).map(([cat, rows]) => (
            <Card key={cat} hover={false}>
              <div className="flex items-center justify-between mb-3">
                <div className="label-eyebrow capitalize">{cat}</div>
                <div className="text-[11px] text-equine-platinum/50">{rows.length} item{rows.length > 1 ? "s" : ""}</div>
              </div>
              <div className="divide-y divide-white/[0.05]">
                {rows.map((it) => (
                  <div
                    key={it.id}
                    data-testid={`inventory-row-${it.id}`}
                    className="py-3 flex items-center gap-4"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-equine-ivory text-[14px] truncate">{it.name}</div>
                      <div className="text-[11.5px] text-equine-platinum/55 mt-0.5 truncate">
                        {it.vendor ? `${it.vendor} · ` : ""}
                        {it.reorder_at > 0 ? `Reorder at ${it.reorder_at} ${it.unit || ""}` : "No reorder threshold"}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-display text-xl text-equine-ivory leading-none">
                        {it.quantity ?? 0}
                        <span className="text-[11px] text-equine-platinum/50 ml-1">{it.unit}</span>
                      </div>
                      {it.low_stock && (
                        <div className="mt-1">
                          <StatusPill tone="warning" dot>low stock</StatusPill>
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => remove(it.id)}
                      data-testid={`inventory-remove-${it.id}`}
                      aria-label="Remove item"
                      className="text-equine-platinum/50 hover:text-equine-clay p-1.5 rounded-md hover:bg-white/[0.04] tap-44"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add inventory item"
        eyebrow="Operations"
        fields={ADD_FIELDS}
        endpoint="/inventory"
        submitLabel="Add item"
        testidPrefix="inventory-add"
        renderWarnings={renderWarnings}
        onCreated={load}
      />

      {/* Mobile FAB — aisle-side quick add */}
      <button
        type="button"
        onClick={() => setAddOpen(true)}
        className="fab lg:hidden"
        data-testid="inventory-fab"
        aria-label="Add inventory item"
      >
        <Plus strokeWidth={1.8} className="w-7 h-7" />
      </button>
    </div>
  );
}
