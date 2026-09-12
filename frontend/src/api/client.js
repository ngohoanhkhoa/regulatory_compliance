const API_BASE = "";

function getToken() {
  return localStorage.getItem("token") || "";
}

// FastAPI returns `detail` as a string for HTTPException, but as a list of
// validation objects for 422s. Normalise both into a readable message instead
// of letting objects stringify to "[object Object]".
export function formatError(detail, fallback = "Request failed") {
  if (detail == null || detail === "") return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((e) => {
      const loc = Array.isArray(e?.loc)
        ? e.loc.filter((p) => p !== "body").join(".")
        : "";
      const msg = e?.msg || (typeof e === "string" ? e : JSON.stringify(e));
      return loc ? `${loc}: ${msg}` : msg;
    });
    return parts.join("; ") || fallback;
  }
  if (typeof detail === "object") return detail.msg || JSON.stringify(detail);
  return String(detail);
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
    const err = new Error(formatError(detail.detail, `HTTP ${res.status}`));
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
    let d = {};
    try {
      d = await res.json();
    } catch {
      /* non-JSON error */
    }
    throw new Error(formatError(d.detail, "Login failed"));
  }
  const { access_token } = await res.json();
  localStorage.setItem("token", access_token);
  return access_token;
}

export async function getMe() {
  return request("/auth/me");
}

export async function updateUsername(username) {
  return request("/auth/me/username", { method: "PUT", body: { username } });
}

export async function updatePassword(currentPassword, newPassword) {
  return request("/auth/me/password", {
    method: "PUT",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

// --- admin: user management --------------------------------------------------

export async function listUsers() {
  return request("/api/admin/users");
}

export async function createUser(payload) {
  return request("/api/admin/users", { method: "POST", body: payload });
}

export async function adminSetUsername(userId, username) {
  return request(`/api/admin/users/${userId}/username`, {
    method: "PUT",
    body: { username },
  });
}

export async function adminSetPassword(userId, newPassword) {
  return request(`/api/admin/users/${userId}/password`, {
    method: "PUT",
    body: { new_password: newPassword },
  });
}

export async function adminSetAdmin(userId, isAdmin) {
  return request(`/api/admin/users/${userId}/admin`, {
    method: "PUT",
    body: { is_admin: isAdmin },
  });
}

export async function deleteUser(userId) {
  return request(`/api/admin/users/${userId}`, { method: "DELETE" });
}

export function logout() {
  localStorage.removeItem("token");
}

export async function chat(question, opts = {}) {
  return request("/chat", {
    method: "POST",
    body: {
      question,
      filters: opts.filters || null,
      include_repealed: opts.include_repealed || false,
      top_k: opts.top_k || null,
      dataset_ids:
        opts.dataset_ids && opts.dataset_ids.length ? opts.dataset_ids : null,
      document_ids:
        opts.document_ids && opts.document_ids.length ? opts.document_ids : null,
      celex_ids:
        opts.celex_ids && opts.celex_ids.length ? opts.celex_ids : null,
    },
  });
}

export async function getHistory(limit = 50) {
  return request(`/history?limit=${limit}`);
}

export async function deleteHistory(queryLogId) {
  return request(`/history/${queryLogId}`, { method: "DELETE" });
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

export async function getTopics() {
  return request("/api/topics");
}

export async function createTopic(topic) {
  return request("/api/topics", { method: "POST", body: topic });
}

export async function updateTopic(topicId, topic) {
  return request(`/api/topics/${topicId}`, { method: "PUT", body: topic });
}

export async function deleteTopic(topicId) {
  return request(`/api/topics/${topicId}`, { method: "DELETE" });
}

export async function getTopicTimeline(topicId) {
  return request(`/api/topics/${topicId}/timeline`);
}

export async function refreshTopic(topicId) {
  return request(`/api/topics/${topicId}/refresh`, { method: "POST" });
}

// --- personal documents ------------------------------------------------------

export async function getDocuments() {
  return request("/api/documents");
}

export async function uploadDocument(file, tags = "") {
  const form = new FormData();
  form.append("file", file);
  if (tags) form.append("tags", tags);
  return request("/api/documents", { method: "POST", body: form });
}

export async function deleteDocument(documentId) {
  return request(`/api/documents/${documentId}`, { method: "DELETE" });
}

export async function searchDocuments(query, topK = 5) {
  return request("/api/documents/search", {
    method: "POST",
    body: { query, top_k: topK },
  });
}

// --- datasets ----------------------------------------------------------------

export async function getDatasets() {
  return request("/api/datasets");
}

export async function getDataset(datasetId) {
  return request(`/api/datasets/${datasetId}`);
}

export async function getDatasetActs(
  datasetId,
  { query = "", limit = 25, offset = 0, sort = null, order = null } = {}
) {
  const params = new URLSearchParams({
    query,
    limit: String(limit),
    offset: String(offset),
  });
  if (sort) params.set("sort", sort);
  if (order) params.set("order", order);
  return request(`/api/datasets/${datasetId}/acts?${params.toString()}`);
}

export async function getDatasetItem(datasetId, itemId) {
  return request(
    `/api/datasets/${datasetId}/items/${encodeURIComponent(itemId)}`
  );
}

export async function importDataset(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/datasets/import", { method: "POST", body: form });
}

export async function deleteDataset(datasetId) {
  return request(`/api/datasets/${datasetId}`, { method: "DELETE" });
}

export async function downloadDataset(datasetId, includeEmbeddings = true) {
  const token = getToken();
  const res = await fetch(
    `/api/datasets/${datasetId}/export?include_embeddings=${includeEmbeddings}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  );
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  return { blob, filename: match ? match[1] : `dataset-${datasetId}.zip` };
}