import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader } from "../components/Primitives";

export default function Owners() {
  const [owners, setOwners] = useState([]);
  useEffect(() => { api.get("/owners").then((r) => setOwners(r.data)); }, []);

  return (
    <div data-testid="owners-page">
      <PageHeader eyebrow="Clients" title="Owners" subtitle="Contact details and horse holdings for every client at the facility." />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {owners.map((o) => (
          <Card key={o.id} data-testid={`owner-${o.id}`}>
            <div className="font-display text-2xl text-equine-ivory">{o.full_name}</div>
            <div className="text-[13px] text-equine-silver/80 mt-1">{o.email}</div>
            <div className="text-[12.5px] text-equine-platinum/60 mt-0.5">{o.phone}</div>
          </Card>
        ))}
      </div>
    </div>
  );
}
