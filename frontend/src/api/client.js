const API_BASE = "";

function getToken() {
  return localStorage.getItem("token") || "";
}

async function request(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(API_BASE + path, { ...opts, headers });
  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = { detail: res.statusText };
    }
    const err = new Error(detail.detail || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = detail;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function register(username, password) {
  return request("/auth/register", {
    method: "POST",
    body: { username, password },
  });
}

export async function login(username, password) {
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) {
    const d = await res.json();
    throw new Error(d.detail || "Login failed");
  }
  const { access_token } = await res.json();
  localStorage.setItem("token", access_token);
  return access_token;
}

export async function getMe() {
  return request("/auth/me");
}

export function logout() {
  localStorage.removeItem("token");
}

export async function query(question, opts = {}) {
  return request("/query", {
    method: "POST",
    body: {
      question,
      filters: opts.filters || null,
      include_repealed: opts.include_repealed || false,
      top_k: opts.top_k || null,
    },
  });
}

export async function getHistory(limit = 50) {
  return request(`/history?limit=${limit}`);
}

export async function submitFeedback(queryLogId, rating, comment) {
  return request("/feedback", {
    method: "POST",
    body: { query_log_id: queryLogId, rating, comment },
  });
}

export async function getHealth() {
  return request("/health");
}

export async function getAct(celex) {
  return request(`/acts/${celex}`);
}