import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";

/**
 * Final pre-launch review — calm "you're ready to ride" summary.
 * Pure read-only, fetches every collection in parallel and presents
 * counts. No mutations, no analytics.
 */
const ReviewStep = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get("/barn"),
      api.get("/locations"),
      api.get("/owners"),
      api.get("/horses"),
      api.get("/riders"),
      api.get("/feed-templates"),
      api.get("/inventory"),
      api.get("/invites").catch(() => ({ data: [] })),
      api.get("/recurring-schedules"),
    ]).then(([barn, locations, owners, horses, riders, feeds, inv, staff, sched]) => {
      setData({
        barn: barn.data, locations: locations.data, owners: owners.data,
        horses: horses.data, riders: riders.data, feeds: feeds.data,
        inv: inv.data, staff: staff.data, sched: sched.data,
      });
    });
  }, []);

  if (!data) return <div className="text-equine-platinum/60">Loading review…</div>;

  const summary = [
    { label: "Locations",            value: data.locations.length, hint: "stalls / paddocks / arenas" },
    { label: "Owners",               value: data.owners.length,    hint: "clients" },
    { label: "Horses",               value: data.horses.length,    hint: "active in barn" },
    { label: "Riders",               value: data.riders.length,    hint: "active program" },
    { label: "Feed templates",       value: data.feeds.length,     hint: "daily meals" },
    { label: "Inventory items",      value: data.inv.length,       hint: "tracked stock" },
    { label: "Staff invites",        value: data.staff.length,     hint: "team" },
    { label: "Recurring schedules",  value: data.sched.length,     hint: "routines" },
  ];

  return (
    <div data-testid="step-review">
      <p className="text-equine-silver/70 text-[14px] mb-5">
        Final review before launching daily operations. You can continue adding records anytime from each module.
      </p>
      <div className="mb-5">
        <div className="label-eyebrow mb-1">Barn</div>
        <div className="font-display text-2xl text-equine-ivory">{data.barn.name || "Unnamed barn"}</div>
        <div className="text-[13px] text-equine-platinum/70 mt-0.5">
          {data.barn.facility_type} · {data.barn.address || "—"} · {data.barn.timezone}
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {summary.map((s) => (
          <div key={s.label} className="rounded-xl bg-equine-soft border border-equine-graphite/40 p-4">
            <div className="label-eyebrow">{s.label}</div>
            <div className="font-display text-3xl text-equine-ivory mt-1">{s.value}</div>
            <div className="text-[11.5px] text-equine-platinum/60 mt-0.5">{s.hint}</div>
          </div>
        ))}
      </div>
      <div className="mt-6 p-4 rounded-xl bg-equine-steel/15 border border-equine-steel/40">
        <div className="text-equine-ivory text-[14px] font-medium mb-1">You&apos;re ready to ride.</div>
        <div className="text-[12.5px] text-equine-platinum/70">
          Click <span className="text-equine-champagne">Launch barn</span> to mark setup complete. Daily operations, feed cards, and the barn board will reflect everything you configured above.
        </div>
      </div>
    </div>
  );
};

export default ReviewStep;
