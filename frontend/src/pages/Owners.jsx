import React, { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";
import { api } from "../lib/api";
import { Card, PageHeader, Empty } from "../components/Primitives";
import QuickAddSheet from "../components/QuickAddSheet";

const ADD_FIELDS = [
  { key: "full_name", label: "Full name", required: true, placeholder: "Charlotte Vance", full: true },
  { key: "email", label: "Email", type: "email", placeholder: "charlotte@example.com" },
  { key: "phone", label: "Phone", placeholder: "+1 555 0142" },
];

export default function Owners() {
  const [owners, setOwners] = useState([]);
  const [q, setQ] = useState("");
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(() => api.get("/owners").then((r) => setOwners(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const filtered = owners.filter((o) =>
    [o.full_name, o.email, o.phone].some((v) => (v || "").toLowerCase().includes(q.toLowerCase()))
  );

  return (
    <div data-testid="owners-page">
      <PageHeader
        eyebrow="Clients"
        title="Owners"
        subtitle="Contact details and horse holdings for every client at the facility."
        action={
          <button
            onClick={() => setAddOpen(true)}
            data-testid="owners-add-btn"
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> Add owner
          </button>
        }
      />

      {owners.length > 0 && (
        <Card hover={false} className="mb-6 !py-3 flex items-center gap-3">
          <Search strokeWidth={1.5} className="w-4 h-4 text-equine-platinum/60" />
          <input
            placeholder="Search owners…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            data-testid="owner-search"
            className="flex-1 bg-transparent outline-none text-equine-ivory placeholder:text-equine-platinum/40 py-1"
          />
        </Card>
      )}

      {owners.length === 0 ? (
        <Empty>
          <div className="font-display text-2xl text-equine-ivory mb-1">No owners yet</div>
          <div className="text-[13px] text-equine-platinum/60 mb-4">Add your first client to start associating horses & invoices.</div>
          <button onClick={() => setAddOpen(true)} data-testid="owners-empty-add" className="btn-primary inline-flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add first owner
          </button>
        </Empty>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((o) => (
            <Card key={o.id} data-testid={`owner-${o.id}`}>
              <div className="font-display text-2xl text-equine-ivory">{o.full_name}</div>
              <div className="text-[13px] text-equine-silver/80 mt-1">{o.email}</div>
              <div className="text-[12.5px] text-equine-platinum/60 mt-0.5">{o.phone}</div>
            </Card>
          ))}
        </div>
      )}

      <QuickAddSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add owner"
        eyebrow="Clients"
        fields={ADD_FIELDS}
        endpoint="/owners"
        submitLabel="Add owner"
        testidPrefix="owners-add"
        onCreated={load}
      />
    </div>
  );
}
