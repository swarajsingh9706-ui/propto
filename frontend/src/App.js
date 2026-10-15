import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "sonner";
import { Loader2 } from "lucide-react";
import Layout from "@/components/Layout";

import Login from "@/pages/SocietyLogin";
import SuperAdminLogin from "@/pages/SuperAdminLogin";
import Societies from "@/pages/super/Societies";
import SuperDashboard from "@/pages/super/SuperDashboard";
import SuperWhatsApp from "@/pages/super/SuperWhatsApp";
import SuperReports from "@/pages/super/SuperReports";
import Dashboard from "@/pages/society/Dashboard";
import Tickets from "@/pages/society/Tickets";
import Vendors from "@/pages/society/Vendors";
import Residents from "@/pages/society/Residents";
import SuperAIActivity from "@/pages/super/SuperAIActivity";
import Notifications from "@/pages/society/Notifications";
import Assets from "@/pages/society/Assets";
import Escalated from "@/pages/society/Escalated";
import Committee from "@/pages/society/Committee";
import AssignmentLogic from "@/pages/society/AssignmentLogic";
import Suggestions from "@/pages/society/Suggestions";
import AuditLog from "@/pages/society/AuditLog";
import Reports from "@/pages/society/Reports";
import ChangePassword from "@/pages/society/ChangePassword";
import Join from "@/pages/public/Join";
import TicketView from "@/pages/public/TicketView";
import VendorTicketView from "@/pages/public/VendorTicketView";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function HomeRedirect() {
  const { user } = useAuth();
  if (user === null) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "super_admin" ? "/super/dashboard" : "/dashboard"} replace />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" richColors />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/admin/login" element={<SuperAdminLogin />} />
            <Route path="/join/:token" element={<Join />} />
            <Route path="/t/:token" element={<TicketView />} />
            <Route path="/v/:token" element={<VendorTicketView />} />
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/super/dashboard" element={<Protected><SuperDashboard /></Protected>} />
            <Route path="/super/societies" element={<Protected><Societies /></Protected>} />
            <Route path="/super/whatsapp" element={<Protected><SuperWhatsApp /></Protected>} />
            <Route path="/super/reports" element={<Protected><SuperReports /></Protected>} />
            <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
            <Route path="/tickets" element={<Protected><Tickets /></Protected>} />
            <Route path="/vendors" element={<Protected><Vendors /></Protected>} />
            <Route path="/residents" element={<Protected><Residents /></Protected>} />
            <Route path="/super/ai-activity" element={<Protected><SuperAIActivity /></Protected>} />
            <Route path="/notifications" element={<Protected><Notifications /></Protected>} />
            <Route path="/assets" element={<Protected><Assets /></Protected>} />
            <Route path="/escalated" element={<Protected><Escalated /></Protected>} />
            <Route path="/committee" element={<Protected><Committee /></Protected>} />
            <Route path="/assignment-logic" element={<Protected><AssignmentLogic /></Protected>} />
            <Route path="/suggestions" element={<Protected><Suggestions /></Protected>} />
            <Route path="/audit" element={<Protected><AuditLog /></Protected>} />
            <Route path="/reports" element={<Protected><Reports /></Protected>} />
            <Route path="/change-password" element={<Protected><ChangePassword /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
