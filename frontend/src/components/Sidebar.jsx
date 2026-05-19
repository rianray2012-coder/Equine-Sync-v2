import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Tablet, Cat, UserCircle2, Users, GraduationCap, Dumbbell,
  Stethoscope, BedDouble, Pill, Trees, UtensilsCrossed, Package, Trophy, Receipt,
  FileText, AlertTriangle, Wrench, ClipboardList, MessageSquare, BarChart3, Settings,
  LogOut, Crown, Sparkles
} from "lucide-react";
import { Logo } from "./Logo";
import { useAuth } from "../context/AuthContext";

const NAV_SECTIONS = [
  {
    label: "Daily",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/barn-board", label: "Barn Board", icon: Tablet },
      { to: "/feed", label: "Feed Room", icon: UtensilsCrossed },
      { to: "/medications", label: "Medications", icon: Pill },
    ],
  },
  {
    label: "Care",
    items: [
      { to: "/horses", label: "Horses", icon: Cat },
      { to: "/health", label: "Health & Vet", icon: Stethoscope },
      { to: "/stall-rest", label: "Stall Rest & Rehab", icon: BedDouble },
      { to: "/turnout", label: "Turnout & Pastures", icon: Trees },
    ],
  },
  {
    label: "Program",
    items: [
      { to: "/riders", label: "Riders", icon: UserCircle2 },
      { to: "/lessons", label: "Lessons", icon: GraduationCap },
      { to: "/training", label: "Training", icon: Dumbbell },
      { to: "/shows", label: "Shows", icon: Trophy },
    ],
  },
  {
    label: "Business",
    items: [
      { to: "/owners", label: "Owners", icon: Users },
      { to: "/owner-portal", label: "Owner Portal", icon: Crown },
      { to: "/billing", label: "Billing", icon: Receipt },
      { to: "/messaging", label: "Messaging", icon: MessageSquare },
    ],
  },
  {
    label: "Operations",
    items: [
      { to: "/inventory", label: "Inventory", icon: Package },
      { to: "/maintenance", label: "Maintenance", icon: Wrench },
      { to: "/incidents", label: "Incidents", icon: AlertTriangle },
      { to: "/staff", label: "Staff", icon: ClipboardList },
      { to: "/documents", label: "Documents", icon: FileText },
    ],
  },
  {
    label: "Insights",
    items: [
      { to: "/reports", label: "Reports", icon: BarChart3 },
      { to: "/onboarding", label: "Barn Setup", icon: Sparkles },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export default function Sidebar({ onNavigate }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="h-full w-[290px] bg-equine-black border-r border-equine-graphite/40 flex flex-col" data-testid="sidebar">
      {/* Header */}
      <div className="px-6 pt-7 pb-5 border-b border-equine-graphite/35">
        <Logo />
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto scrollbar-luxe py-4 px-3">
        {NAV_SECTIONS.map((sec, si) => (
          <div key={sec.label} className={si > 0 ? "mt-5" : ""}>
            <div className="px-3 pb-2 text-[9.5px] tracking-[0.28em] uppercase text-equine-brass/65 font-semibold">{sec.label}</div>
            {sec.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z]+/g, '-')}`}
                  className={({ isActive }) =>
                    `relative group flex items-center gap-3.5 px-3.5 py-2.5 rounded-xl mb-0.5 transition-all duration-200 tap-44 ${
                      isActive
                        ? "nav-active-rail bg-gradient-to-r from-equine-brass/15 via-equine-saddle/8 to-transparent text-equine-cream border border-equine-brass/25"
                        : "text-equine-silver/75 hover:bg-equine-soft/70 hover:text-equine-ivory hover:border-equine-graphite/40 border border-transparent"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon strokeWidth={1.5} className={`w-[18px] h-[18px] transition-colors ${isActive ? "text-equine-brassLight" : "group-hover:text-equine-brass/80"}`} />
                      <span className="text-[13.5px] tracking-wide flex-1">{item.label}</span>
                      {isActive && <span className="w-1 h-1 rounded-full bg-equine-brass shadow-[0_0_8px_rgba(184,153,104,0.7)]" />}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User & sign out */}
      <div className="px-3 pb-5 pt-4 border-t border-equine-graphite/35">
        {user && (
          <div className="px-3 py-2.5 rounded-xl bg-gradient-to-br from-equine-elevated to-equine-soft mb-2 flex items-center gap-3 border border-equine-graphite/40">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-equine-brass to-equine-saddle flex items-center justify-center font-display text-lg text-equine-black shadow-inner">
              {user.full_name?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] text-equine-ivory truncate">{user.full_name}</div>
              <div className="text-[9.5px] uppercase tracking-[0.22em] text-equine-brass/75 mt-0.5">{user.role.replace(/_/g, ' ')}</div>
            </div>
          </div>
        )}
        <button
          onClick={() => { logout(); navigate("/login"); }}
          data-testid="logout-btn"
          className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-equine-silver/65 hover:text-equine-clay hover:bg-equine-soft/60 transition-colors tap-44"
        >
          <LogOut strokeWidth={1.5} className="w-[18px] h-[18px]" />
          <span className="text-[13px]">Sign out</span>
        </button>
      </div>
    </aside>
  );
}
