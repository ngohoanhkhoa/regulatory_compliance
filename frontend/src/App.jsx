import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./api/AuthContext";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import History from "./pages/History";
import "./styles/main.css";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function NavBar() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <nav className="navbar">
      <div className="navbar-brand">EU RegCompliance</div>
      <div className="navbar-links">
        <NavLink to="/chat" className={({ isActive }) => isActive ? "active" : ""}>Chat</NavLink>
        <NavLink to="/history" className={({ isActive }) => isActive ? "active" : ""}>History</NavLink>
      </div>
      <div className="navbar-user">
        <span>{user.username}</span>
        {user.is_admin && <span className="admin-badge">admin</span>}
        <button onClick={signOut}>Sign Out</button>
      </div>
    </nav>
  );
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading…</div>;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  return (
    <>
      <NavBar />
      <main className="main-content">
        <Routes>
          <Route path="/chat" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}