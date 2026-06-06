import React from "react";
import "./App.css";
import "./index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "sonner";

import AppShell from "./components/AppShell";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
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
import Inventory from "./pages/Inventory";
import Settings from "./pages/Settings";
import Placeholder from "./pages/Placeholder";
import Onboarding from "./pages/Onboarding";
import AcceptInvite from "./pages/AcceptInvite";
import ResetPassword from "./pages/ResetPassword";
import VerifyEmail from "./pages/VerifyEmail";
import Reports from "./pages/Reports";
import ReviewQueue from "./pages/ReviewQueue";
import Today from "./pages/Today";
import Rehab from "./pages/Rehab";
import Turnout from "./pages/Turnout";

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
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route element={<Protected><AppShell /></Protected>}>
              <Route index element={<Dashboard />} />
              <Route path="/today" element={<Today />} />
              <Route path="/barn-board" element={<Navigate to="/today" replace />} />
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/horses" element={<Horses />} />
              <Route path="/horses/:id" element={<HorseProfile />} />
              <Route path="/riders" element={<Riders />} />
              <Route path="/owners" element={<Owners />} />
              <Route path="/lessons" element={<Lessons />} />
              <Route path="/training" element={<Training />} />
              <Route path="/health" element={<Health />} />
              <Route path="/stall-rest" element={<Rehab />} />
              <Route path="/rehab" element={<Navigate to="/stall-rest" replace />} />
              <Route path="/medications" element={<Medications />} />
              <Route path="/turnout" element={<Turnout />} />
              <Route path="/feed" element={<Feed />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/billing" element={<Billing />} />
              <Route path="/review-queue" element={<ReviewQueue />} />
              <Route path="/incidents" element={<Incidents />} />
              {/* Removed for founder beta — Shows / Documents / Maintenance / Staff
                  redirect to safe destinations so old bookmarks don't 404. */}
              <Route path="/shows" element={<Navigate to="/" replace />} />
              <Route path="/documents" element={<Navigate to="/horses" replace />} />
              <Route path="/maintenance" element={<Navigate to="/incidents" replace />} />
              <Route path="/staff" element={<Navigate to="/settings" replace />} />
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
