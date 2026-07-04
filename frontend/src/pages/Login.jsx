import { useState } from "react";
import { useAuth } from "../api/AuthContext";

export default function Login() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
        <h1>EU Regulatory Compliance</h1>
        <p className="subtitle">
          Ask questions about EU legal obligations. Answers are grounded in the
          CEPS EurLex dataset.
        </p>
        <div className="login-tabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
          >
            Sign In
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>
        <form onSubmit={submit}>
          <input
            type="text"
            placeholder="Username (min 3 chars)"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            required
          />
          <input
            type="password"
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign In" : "Register & Sign In"}
          </button>
        </form>
        <p className="cutoff-notice">
          Dataset frozen at August 2019 — recent legislation may be missing.
        </p>
      </div>
    </div>
  );
}

import * as api from "../api/client";