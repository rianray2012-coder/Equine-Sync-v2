import React from "react";
import "./App.css";
import "./index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "sonner";

import AppShell from "./components/AppShell";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import BarnBoard from "./pages/BarnBoard";
import Horses from "./pages/Horses";
import HorseProfile from "./pages/HorseProfile";
import Riders from "./pages/Riders";
import Owners from "./pages/Owners";
import Lessons from "./pages/Lessons";
import Training from "./pages/Training";
import Health from "./pages/Health";
import Medications from "./pages/Medications";
import Feed from "./pages/Feed";
import Billing from "./pages/Billing";
import Messaging from "./pages/Messaging";
import OwnerPortal from "./pages/OwnerPortal";
import Incidents from "./pages/Incidents";
import Settings from "./pages/Settings";
import Placeholder from "./pages/Placeholder";
import Onboarding from "./pages/Onboarding";
import AcceptInvite from "./pages/AcceptInvite";
import Reports from "./pages/Reports";

const Protected = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-equine-platinum/60">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Toaster position="top-right" theme="dark" />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/accept-invite" element={<AcceptInvite />} />
            <Route element={<Protected><AppShell /></Protected>}>
              <Route index element={<Dashboard />} />
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/barn-board" element={<BarnBoard />} />
              <Route path="/horses" element={<Horses />} />
              <Route path="/horses/:id" element={<HorseProfile />} />
              <Route path="/riders" element={<Riders />} />
              <Route path="/owners" element={<Owners />} />
              <Route path="/lessons" element={<Lessons />} />
              <Route path="/training" element={<Training />} />
              <Route path="/health" element={<Health />} />
              <Route path="/stall-rest" element={<Placeholder title="Stall Rest & Rehab" description="Hand-walking schedules, icing, and daily rehab logs." />} />
              <Route path="/medications" element={<Medications />} />
              <Route path="/turnout" element={<Placeholder title="Turnout & Pastures" description="Herd compatibility, mud levels and rotation schedules." />} />
              <Route path="/feed" element={<Feed />} />
              <Route path="/inventory" element={<Placeholder title="Inventory" description="Grain, hay, bedding, supplements with reorder alerts." />} />
              <Route path="/shows" element={<Placeholder title="Shows & Competitions" description="Show calendars, entries, stabling and packing lists." />} />
              <Route path="/billing" element={<Billing />} />
              <Route path="/documents" element={<Placeholder title="Documents" description="Secure document vault for vaccines, insurance and contracts." />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/maintenance" element={<Placeholder title="Maintenance" description="Tickets for fences, gates, waterers and arenas." />} />
              <Route path="/staff" element={<Placeholder title="Staff Management" description="Workloads, certifications and shift scheduling." />} />
              <Route path="/messaging" element={<Messaging />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/owner-portal" element={<OwnerPortal />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
