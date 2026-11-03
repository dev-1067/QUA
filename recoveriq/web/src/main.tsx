import "./index.css";
import { lazy, Suspense, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";
import { RoleGate, Shell } from "./components/Shell";
import { Spinner, ToastProvider } from "./components/ui";
import { AuthProvider, can, useAuth } from "./lib/auth";
import Login from "./pages/Login";

registerSW({ immediate: true });

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Cases = lazy(() => import("./pages/Cases"));
const CaseDetail = lazy(() => import("./pages/CaseDetail"));
const Intake = lazy(() => import("./pages/Intake"));
const Allocation = lazy(() => import("./pages/Allocation"));
const FieldMap = lazy(() => import("./pages/FieldMap"));
const Promises = lazy(() => import("./pages/Promises"));
const Disputes = lazy(() => import("./pages/Disputes"));
const Payments = lazy(() => import("./pages/Payments"));
const Notifications = lazy(() => import("./pages/Notifications"));
const Sentiment = lazy(() => import("./pages/Sentiment"));
const Leaderboard = lazy(() => import("./pages/Leaderboard"));
const Rules = lazy(() => import("./pages/Rules"));
const Models = lazy(() => import("./pages/Models"));
const Audit = lazy(() => import("./pages/Audit"));
const Compliance = lazy(() => import("./pages/Compliance"));
const AgentApp = lazy(() => import("./agent/AgentApp"));
const PayPage = lazy(() => import("./public/PayPage"));
const Checkout = lazy(() => import("./public/Checkout"));

function Loading() {
  return <div className="min-h-[50vh] flex items-center justify-center text-muted"><Spinner size={20} /></div>;
}

function RequireManager({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />;
  if (user.role === "agent") return <Navigate to="/agent" replace />;
  return <>{children}</>;
}

function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "agent" ? "/agent" : "/app"} replace />;
}

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/agent/*" element={<AgentApp />} />
        <Route path="/p/:token" element={<PayPage />} />
        <Route path="/gateway/checkout/:linkId" element={<Checkout />} />
        <Route path="/app" element={<RequireManager><Shell /></RequireManager>}>
          <Route index element={<Dashboard />} />
          <Route path="cases" element={<Cases />} />
          <Route path="cases/:id" element={<CaseDetail />} />
          <Route path="intake" element={<RoleGate allow={can.intake}><Intake /></RoleGate>} />
          <Route path="allocation" element={<Allocation />} />
          <Route path="field" element={<FieldMap />} />
          <Route path="promises" element={<Promises />} />
          <Route path="disputes" element={<Disputes />} />
          <Route path="payments" element={<Payments />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="sentiment" element={<Sentiment />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="rules" element={<Rules />} />
          <Route path="models" element={<RoleGate allow={can.models}><Models /></RoleGate>} />
          <Route path="audit" element={<RoleGate allow={can.audit}><Audit /></RoleGate>} />
          <Route path="compliance" element={<RoleGate allow={can.compliance}><Compliance /></RoleGate>} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center text-center p-6">
      <div className="font-mono text-faint text-[13px]">404</div>
      <h1 className="text-[20px] font-semibold mt-1">This page doesn't exist</h1>
      <a href="/" className="btn-primary mt-5">Go home</a>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <AuthProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </AuthProvider>
  </BrowserRouter>,
);
