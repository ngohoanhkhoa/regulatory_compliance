import { useState } from "react";
import { useAuth } from "../api/AuthContext";
import * as api from "../api/client";
import { Shield, BookOpen, User, Lock, AlertCircle } from "lucide-react";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";

export default function Login() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("0000");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "register") {
        await api.register(username, password);
      }
      await signIn(username, password);
    } catch (err) {
      setError(err.message || "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="logo">
          <Shield className="w-8 h-8 text-[var(--accent)]" />
          <h1>EU Regulatory Compliance</h1>
        </div>

        <p className="subtitle">
          AI-powered answers about EU legal obligations, grounded in the
          CEPS EurLex dataset with full citations.
        </p>

        <div className="login-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => { setMode("login"); setError(""); }}
          >
            <User className="w-4 h-4 inline mr-1" />
            Sign In
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setError("");
              if (username === "admin") setUsername("");
              setPassword("");
            }}
          >
            <BookOpen className="w-4 h-4 inline mr-1" />
            Register
          </button>
        </div>

        <form onSubmit={submit}>
          <Input
            icon={User}
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            required
          />
          <Input
            icon={Lock}
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={mode === "register" ? 8 : undefined}
            required
          />
          {mode === "register" && (
            <p className="field-hint">
              Username ≥ 3 characters, password ≥ 8 characters.
            </p>
          )}

          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-[var(--bad-muted)] border border-[var(--bad)] text-[var(--bad)] text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            isLoading={busy}
            className="w-full"
          >
            {mode === "login" ? "Sign In" : "Create Account"}
          </Button>
        </form>
      </div>
    </div>
  );
}
