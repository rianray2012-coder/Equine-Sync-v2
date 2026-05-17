import React from "react";
import { useAuth } from "../context/AuthContext";
import { Card, PageHeader } from "../components/Primitives";

export default function Settings() {
  const { user } = useAuth();
  return (
    <div data-testid="settings-page">
      <PageHeader eyebrow="Account" title="Settings" subtitle="Account, facility, and team preferences." />
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><div className="label-eyebrow">Name</div><div className="text-equine-ivory mt-1">{user?.full_name}</div></div>
          <div><div className="label-eyebrow">Email</div><div className="text-equine-ivory mt-1">{user?.email}</div></div>
          <div><div className="label-eyebrow">Role</div><div className="text-equine-ivory mt-1 capitalize">{user?.role?.replace('_', ' ')}</div></div>
          <div><div className="label-eyebrow">Facility</div><div className="text-equine-ivory mt-1">Whitfield Equestrian Estate</div></div>
        </div>
      </Card>
    </div>
  );
}
