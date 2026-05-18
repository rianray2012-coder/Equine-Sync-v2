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

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/onboarding", label: "Barn Setup", icon: Sparkles },
  { to: "/barn-board", label: "Barn Board", icon: Tablet },
  { to: "/horses", label: "Horses", icon: Cat },
  { to: "/riders", label: "Riders", icon: UserCircle2 },
  { to: "/owners", label: "Owners", icon: Users },
  { to: "/lessons", label: "Lessons", icon: GraduationCap },
  { to: "/training", label: "Training", icon: Dumbbell },
  { to: "/health", label: "Health & Vet", icon: Stethoscope },
  { to: "/stall-rest", label: "Stall Rest & Rehab", icon: BedDouble },
  { to: "/medications", label: "Medications", icon: Pill },
  { to: "/turnout", label: "Turnout & Pastures", icon: Trees },
  { to: "/feed", label: "Feed Room", icon: UtensilsCrossed },
  { to: "/inventory", label: "Inventory", icon: Package },
  { to: "/shows", label: "Shows", icon: Trophy },
  { to: "/billing", label: "Billing", icon: Receipt },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/maintenance", label: "Maintenance", icon: Wrench },
  { to: "/staff", label: "Staff", icon: ClipboardList },
  { to: "/messaging", label: "Messaging", icon: MessageSquare },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/owner-portal", label: "Owner Portal", icon: Crown },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar({ onNavigate }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="h-full w-72 bg-equine-black border-r border-equine-graphite/40 flex flex-col" data-testid="sidebar">
      <div className="px-6 py-6 border-b border-equine-graphite/30">
        <Logo />
      </div>
      <nav className="flex-1 overflow-y-auto scrollbar-luxe py-3 px-3">
        {NAV.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z]+/g, '-')}`}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-lg mb-0.5 transition-all duration-200 ${
                  isActive
                    ? "bg-equine-steel/30 text-equine-ivory border border-equine-steel/40"
                    : "text-equine-silver/80 hover:bg-equine-soft hover:text-equine-ivory"
                }`
              }
            >
              <Icon strokeWidth={1.5} className="w-[18px] h-[18px]" />
              <span className="text-[13.5px] tracking-wide">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="px-3 pb-4 pt-3 border-t border-equine-graphite/30">
        {user && (
          <div className="px-3 py-2.5 rounded-lg bg-equine-soft mb-2 flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-equine-steel/30 flex items-center justify-center font-display text-lg text-equine-ivory">
              {user.full_name?.[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] text-equine-ivory truncate">{user.full_name}</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-equine-platinum/60">{user.role.replace(/_/g, ' ')}</div>
            </div>
          </div>
        )}
        <button
          onClick={() => { logout(); navigate("/login"); }}
          data-testid="logout-btn"
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-equine-silver/70 hover:text-equine-clay hover:bg-equine-soft transition-colors"
        >
          <LogOut strokeWidth={1.5} className="w-[18px] h-[18px]" />
          <span className="text-[13px]">Sign out</span>
        </button>
      </div>
    </aside>
  );
}
