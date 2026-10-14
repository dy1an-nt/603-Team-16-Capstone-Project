// Thin wrapper around the backend API. All calls send the session cookie.
const API_BASE = "http://localhost:8000";

async function apiRequest(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, { credentials: "include", ...options });
  const body = resp.headers.get("content-type")?.includes("application/json")
    ? await resp.json()
    : null;
  if (!resp.ok) {
    throw new Error(body?.detail || `Request failed: ${resp.status}`);
  }
  return body;
}

const api = {
  health: () => apiRequest("/health"),
  register: (email, password) =>
    apiRequest("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  uploadResume: (file) => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest("/resumes", { method: "POST", body: form });
  },
};
