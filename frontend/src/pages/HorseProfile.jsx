import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, fmtDate, money } from "../lib/api";
import { Card, StatusPill } from "../components/Primitives";
import { ArrowLeft } from "lucide-react";
import CuratedTimeline from "../components/CuratedTimeline";
import HorseOwnerUpdates from "../components/HorseOwnerUpdates";
import { useAuth } from "../context/AuthContext";

const BASE_TABS = ["Overview", "Timeline", "Feed", "Training", "Health", "Injuries", "Medications", "Wellness", "Billing", "Owner"];

export default function HorseProfile() {
  const { id } = useParams();
  const { user } = useAuth();
  const canManage = ["admin", "barn_manager", "trainer"].includes(user?.role);
  const TABS = canManage ? [...BASE_TABS, "Updates"] : BASE_TABS;
  const [horse, setHorse] = useState(null);
  const [meds, setMeds] = useState([]);
  const [vet, setVet] = useState([]);
  const [injuries, setInjuries] = useState([]);
  const [wellness, setWellness] = useState([]);
  const [training, setTraining] = useState([]);
  const [tab, setTab] = useState("Overview");

  useEffect(() => {
    api.get(`/horses/${id}`).then((r) => setHorse(r.data));
    api.get(`/medications?horse_id=${id}`).then((r) => setMeds(r.data));
    api.get(`/vet-records?horse_id=${id}`).then((r) => setVet(r.data));
    api.get(`/injuries?horse_id=${id}`).then((r) => setInjuries(r.data));
    api.get(`/wellness?horse_id=${id}`).then((r) => setWellness(r.data));
    api.get(`/training?horse_id=${id}`).then((r) => setTraining(r.data));
  }, [id]);

  if (!horse) return <div className="text-equine-platinum/60">Loading…</div>;

  return (
    <div data-testid="horse-profile-page">
      <Link to="/horses" className="inline-flex items-center gap-2 text-equine-platinum/70 hover:text-equine-ivory mb-6"><ArrowLeft className="w-4 h-4" /> Back to roster</Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Card className="lg:col-span-1 !p-0 overflow-hidden">
          <div className="aspect-[4/3]">
            <img src={horse.photo_url} alt={horse.name} className="w-full h-full object-cover" />
          </div>
          <div className="p-6">
            <div className="label-eyebrow">{horse.discipline}</div>
            <h1 className="font-display text-4xl text-equine-ivory mt-2">{horse.name}</h1>
            <div className="text-equine-silver/70 mt-1">{horse.breed} · {horse.age} yrs · {horse.color} · {horse.height_hands}hh</div>
            <div className="mt-4 flex gap-2 flex-wrap">
              <StatusPill tone={horse.status === "active" ? "success" : horse.status === "stall_rest" ? "critical" : "warning"}>{horse.status.replace('_', ' ')}</StatusPill>
              <StatusPill tone="neutral">{horse.stall}</StatusPill>
              {horse.behavior_flags?.map((f) => <StatusPill key={f} tone="warning">{f}</StatusPill>)}
            </div>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
            <Mini label="Wellness" value={horse.wellness_score} accent="sage" />
            <Mini label="Turnout" value={horse.turnout_group || "—"} small />
            <Mini label="Insurance" value={horse.insurance || "—"} small />
            <Mini label="Allergies" value={horse.allergies?.join(', ') || "None"} small />
          </div>

          <div className="mt-6">
            <div className="label-eyebrow mb-2">Training Goals</div>
            <p className="text-equine-silver/80">{horse.training_goals || "—"}</p>
          </div>
          <div className="mt-4">
            <div className="label-eyebrow mb-2">Emergency Notes</div>
            <p className="text-equine-silver/80">{horse.emergency_notes || "—"}</p>
          </div>
        </Card>
      </div>

      {/* Tabs — horizontally scrollable on mobile; ≥44px hit targets */}
      <div className="relative mb-6">
        <Card hover={false} className="!p-2 overflow-x-auto scrollbar-luxe">
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                data-testid={`tab-${t.toLowerCase()}`}
                className={`px-4 py-3 rounded-lg text-[13px] tracking-wide transition-all tap-44 whitespace-nowrap ${tab === t ? "bg-equine-steel/30 text-equine-ivory border border-equine-steel/40" : "text-equine-platinum/70 hover:bg-equine-soft hover:text-equine-ivory"}`}
              >{t}</button>
            ))}
          </div>
        </Card>
        {/* Soft edge fades hint at horizontal scrollability on small screens. */}
        <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-equine-black to-transparent rounded-r-lg md:hidden" />
        <div aria-hidden className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-equine-black to-transparent rounded-l-lg md:hidden" />
      </div>

      {tab === "Overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card><h3 className="font-display text-2xl mb-3">Feed Plan</h3><p className="text-equine-silver/80 text-[14px] leading-relaxed">{horse.feed_plan}</p></Card>
          <Card><h3 className="font-display text-2xl mb-3">Recent Wellness</h3>
            {wellness.slice(0, 3).map((w) => (
              <div key={w.id} className="py-2 hairline flex justify-between text-[14px]"><span>{fmtDate(w.created_at)}</span><StatusPill tone={w.status === "normal" ? "success" : w.status === "watch" ? "warning" : "critical"}>{w.status}</StatusPill></div>
            ))}
          </Card>
        </div>
      )}
      {tab === "Medications" && <List items={meds} render={(m) => <Row title={m.name} sub={`${m.dosage} · ${m.frequency} · ${m.route}`} right={m.prescribing_vet} />} />}
      {tab === "Timeline" && <Card><CuratedTimeline horseId={id} limit={60} ownerView={false} /></Card>}
      {tab === "Health" && <List items={vet} render={(v) => <Row title={v.title} sub={`${fmtDate(v.date)} · ${v.vet_name}`} right={money(v.cost)} />} />}
      {tab === "Injuries" && <List items={injuries} render={(i) => <Row title={i.title} sub={i.description} right={<StatusPill tone={i.status === "resolved" ? "success" : "warning"}>{i.status}</StatusPill>} />} />}
      {tab === "Wellness" && <List items={wellness} render={(w) => <Row title={`Wellness check · ${fmtDate(w.created_at)}`} sub={`Appetite ${w.appetite}/5 · Energy ${w.energy}/5 · Coat ${w.coat_quality}/5`} right={<StatusPill tone={w.status === "normal" ? "success" : "warning"}>{w.status}</StatusPill>} />} />}
      {tab === "Training" && <List items={training} render={(t) => <Row title={`${fmtDate(t.date)} · ${t.discipline}`} sub={t.exercises} right={`Rating ${t.rating}/10`} />} />}
      {tab === "Feed" && <Card><p className="text-equine-silver/80">{horse.feed_plan}</p></Card>}
      {tab === "Billing" && <Card hover={false}><p className="text-equine-platinum/60">See <Link to="/billing" className="text-equine-champagne">Billing</Link> for full invoice history.</p></Card>}
      {tab === "Owner" && <Card><div className="label-eyebrow mb-2">Owner ID</div><p className="text-equine-silver/80">{horse.owner_id}</p></Card>}
      {tab === "Updates" && canManage && <HorseOwnerUpdates horseId={id} />}
    </div>
  );
}

const Mini = ({ label, value, accent, small }) => (
  <div>
    <div className="label-eyebrow">{label}</div>
    <div className={`mt-2 ${small ? "text-[14px] text-equine-silver" : "font-display text-3xl text-equine-ivory"} ${accent === "sage" ? "text-equine-sage" : ""}`}>{value}</div>
  </div>
);

const Row = ({ title, sub, right }) => (
  <div className="flex items-center justify-between py-4 hairline gap-4">
    <div className="flex-1 min-w-0">
      <div className="text-equine-ivory text-[14.5px]">{title}</div>
      <div className="text-equine-platinum/60 text-[12.5px] mt-0.5 truncate">{sub}</div>
    </div>
    <div className="text-equine-silver/80 text-[13px]">{right}</div>
  </div>
);

const List = ({ items, render }) => (
  <Card>
    {items.length === 0 && <div className="text-equine-platinum/60 text-sm">No records yet.</div>}
    {items.map((it) => <div key={it.id}>{render(it)}</div>)}
  </Card>
);
