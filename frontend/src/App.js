import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Overview from "@/pages/Overview";
import Reports from "@/pages/Reports";
import Uploads from "@/pages/Uploads";
import SalesLedger from "@/pages/SalesLedger";
import Calculations from "@/pages/Calculations";
import Reconciliation from "@/pages/Reconciliation";
import Discrepancies from "@/pages/Discrepancies";
import Masters from "@/pages/Masters";
import { Toaster } from "sonner";

function Shell({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <div className="App dark">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Shell><Overview /></Shell>} />
            <Route path="/reports" element={<Shell><Reports /></Shell>} />
            <Route path="/uploads" element={<Shell><Uploads /></Shell>} />
            <Route path="/sales" element={<Shell><SalesLedger /></Shell>} />
            <Route path="/calculations" element={<Shell><Calculations /></Shell>} />
            <Route path="/reconciliation" element={<Shell><Reconciliation /></Shell>} />
            <Route path="/discrepancies" element={<Shell><Discrepancies /></Shell>} />
            <Route path="/masters" element={<Shell><Masters /></Shell>} />
          </Routes>
        </BrowserRouter>
        <Toaster
          theme="dark"
          position="top-right"
          toastOptions={{
            style: { background: "#0a0a0a", border: "1px solid #2a2a2a", fontFamily: "JetBrains Mono", fontSize: 12, borderRadius: 0 },
          }}
        />
      </AuthProvider>
    </div>
  );
}

export default App;
