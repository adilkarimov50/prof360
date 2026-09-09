import { Routes, Route, Navigate } from "react-router-dom";
import { Center, Loader } from "@mantine/core";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Persons from "./pages/Persons";
import PersonCard from "./pages/PersonCard";
import Legal from "./pages/Legal";
import LegalNormPage from "./pages/LegalNormPage";
import AiConsultant from "./pages/AiConsultant";
import Spravka from "./pages/Spravka";
import Upload from "./pages/Upload";
import Admin from "./pages/Admin";
import Audit from "./pages/Audit";
import AnalyticsPage from "./pages/AnalyticsPage";
import DistrictDetail from "./pages/DistrictDetail";
import Settings from "./pages/Settings";
import DataQuality from "./pages/DataQuality";
import CommissionDocs from "./pages/CommissionDocs";
import CommissionDocDetail from "./pages/CommissionDocDetail";
import CommissionAnalytics from "./pages/CommissionAnalytics";
import AdmBlocks from "./pages/AdmBlocks";
import CommissionSessions from "./pages/CommissionSessions";
import CommissionSessionDetail from "./pages/CommissionSessionDetail";
import UnifiedAnalytics from "./pages/UnifiedAnalytics";
import LocalitiesOverview from "./pages/LocalitiesOverview";
import LegalDocumentReader from "./pages/LegalDocumentReader";
import { canAccess } from "./lib/nav";

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <Center h="100vh"><Loader /></Center>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password && !window.location.pathname.startsWith("/settings")) {
    return <Navigate to="/settings?change_password=1" replace />;
  }
  return children;
}

function RoleRoute({ roles, children }: { roles: string[]; children: JSX.Element }) {
  const { user } = useAuth();
  if (!canAccess(user?.role, roles)) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Layout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="persons" element={<Persons />} />
        <Route path="persons/:id" element={<PersonCard />} />
        <Route path="legal" element={<Legal />} />
        <Route path="legal/norms/:id" element={<LegalNormPage />} />
        <Route path="legal/documents/:docId" element={<LegalDocumentReader />} />
        <Route path="ai" element={<AiConsultant />} />
        <Route path="spravka" element={<Spravka />} />
        <Route path="commission" element={<CommissionDocs />} />
        <Route path="commission/:id" element={<CommissionDocDetail />} />
        <Route path="commission-analytics" element={<CommissionAnalytics />} />
        <Route path="adm-blocks" element={<AdmBlocks />} />
        <Route path="commission-sessions" element={<CommissionSessions />} />
        <Route path="commission-sessions/:id" element={<CommissionSessionDetail />} />
        <Route path="district/:name" element={<DistrictDetail />} />
        <Route path="settings" element={<Settings />} />
        <Route path="quality" element={<RoleRoute roles={["admin", "analyst", "oblast_prosecutor", "deputy_prosecutor"]}><DataQuality /></RoleRoute>} />
        <Route path="upload" element={<RoleRoute roles={["admin", "analyst"]}><Upload /></RoleRoute>} />
        <Route path="admin" element={<RoleRoute roles={["admin"]}><Admin /></RoleRoute>} />
        <Route path="audit" element={<RoleRoute roles={["admin", "security_auditor", "oblast_prosecutor"]}><Audit /></RoleRoute>} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="analytics/unified" element={<UnifiedAnalytics />} />
        <Route path="localities" element={<LocalitiesOverview />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
