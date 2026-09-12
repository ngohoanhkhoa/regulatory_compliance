import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./api/AuthContext";
import { ChatProvider } from "./api/ChatContext";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Topics from "./pages/Topics";
import Datasets from "./pages/Datasets";
import DatasetDetail from "./pages/DatasetDetail";
import Settings from "./pages/Settings";
import "./styles/main.css";

function NavBar() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <nav className="navbar">
      <div className="navbar-brand">Regulatory Compliance</div>
      <div className="navbar-links">
        <NavLink to="/chat" className={({ isActive }) => isActive ? "active" : ""}>Chat</NavLink>
        <NavLink to="/topics" className={({ isActive }) => isActive ? "active" : ""}>Topics</NavLink>
        <NavLink to="/datasets" className={({ isActive }) => isActive ? "active" : ""}>Datasets</NavLink>
      </div>
      <div className="navbar-user">
        <NavLink to="/settings" className="navbar-username" title="Account & settings">
          {user.username}
        </NavLink>
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
    <ChatProvider>
      <NavBar />
      <main className="main-content">
        <Routes>
          <Route path="/chat" element={<Chat />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/datasets/:id" element={<DatasetDetail />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>
    </ChatProvider>
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