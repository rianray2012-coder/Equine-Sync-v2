import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Cat, UserCircle2, Users, GraduationCap, Dumbbell,
  Stethoscope, BedDouble, Pill, Trees, UtensilsCrossed, Package, Receipt,
  AlertTriangle, MessageSquare, BarChart3, Settings,
  LogOut, Crown, Sparkles, ListChecks
} from "lucide-react";
import { Logo } from "./Logo";
import { useAuth } from "../context/AuthContext";

const NAV_SECTIONS = [
  {
    label: "Daily",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/today", label: "Today", icon: ListChecks },
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
      { to: "/incidents", label: "Incidents", icon: AlertTriangle },
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
    <aside className="h-full w-[290px] bg-equine-navy border-r border-equine-navyDeep flex flex-col text-equine-platinum/90" data-testid="sidebar">
      {/* Header */}
      <div className="px-6 pt-7 pb-5 border-b border-white/[0.08]">
        <Logo onNavy />
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto scrollbar-luxe py-4 px-3">
        {NAV_SECTIONS.map((sec, si) => (
          <div key={sec.label} className={si > 0 ? "mt-5" : ""}>
            <div className="px-3 pb-2 text-[9.5px] tracking-[0.28em] uppercase text-equine-brassLight/70 font-semibold">{sec.label}</div>
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
                        ? "nav-active-rail bg-gradient-to-r from-equine-brass/20 via-equine-saddle/8 to-transparent text-white border border-white/10"
                        : "text-equine-platinum/80 hover:bg-white/[0.04] hover:text-white border border-transparent"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon strokeWidth={1.5} className={`w-[18px] h-[18px] transition-colors ${isActive ? "text-equine-brassLight" : "group-hover:text-equine-brassLight/90"}`} />
                      <span className="text-[13.5px] tracking-wide flex-1">{item.label}</span>
                      {isActive && <span className="w-1 h-1 rounded-full bg-equine-brassLight shadow-[0_0_10px_rgba(194,205,236,0.9)]" />}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User & sign out */}
      <div className="px-3 pb-5 pt-4 border-t border-white/[0.08]">
        {user && (
          <div className="px-3 py-2.5 rounded-xl bg-white/[0.04] mb-2 flex items-center gap-3 border border-white/[0.08]">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-equine-brassLight to-equine-saddle flex items-center justify-center font-display text-lg text-equine-navy shadow-inner">
              {user.full_name?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] text-white truncate">{user.full_name}</div>
              <div className="text-[9.5px] uppercase tracking-[0.22em] text-equine-brassLight/80 mt-0.5">{user.role.replace(/_/g, ' ')}</div>
            </div>
          </div>
        )}
        <button
          onClick={() => { logout(); navigate("/login"); }}
          data-testid="logout-btn"
          className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-equine-platinum/70 hover:text-equine-clay hover:bg-white/[0.04] transition-colors tap-44"
        >
          <LogOut strokeWidth={1.5} className="w-[18px] h-[18px]" />
          <span className="text-[13px]">Sign out</span>
        </button>
      </div>
    </aside>
  );
}
