// Thin wrapper around the backend API. Calls send the JWT from login as a bearer token.
const API_BASE = "http://localhost:8000";
// sessionStorage, so the token is gone when the tab closes.
const TOKEN_KEY = "accessToken";

function errorMessage(body, status) {
  const detail = body?.detail;
  // FastAPI's own 422 validation errors return a list. Every other error is a string.
  if (Array.isArray(detail)) return detail[0]?.msg || `Request failed: ${status}`;
  return detail || `Request failed: ${status}`;
}

async function apiRequest(path, options = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const headers = { ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  // 204 has no body even when the server labels it JSON.
  const body = resp.status !== 204 && resp.headers.get("content-type")?.includes("application/json")
    ? await resp.json()
    : null;
  if (!resp.ok) {
    if (resp.status === 401) sessionStorage.removeItem(TOKEN_KEY);
    const error = new Error(errorMessage(body, resp.status));
    error.status = resp.status;
    throw error;
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
  login: async (email, password) => {
    const body = await apiRequest("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    sessionStorage.setItem(TOKEN_KEY, body.access_token);
    return body;
  },
  logout: async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } finally {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  },
  deleteAccount: async () => {
    await apiRequest("/account", { method: "DELETE" });
    sessionStorage.removeItem(TOKEN_KEY);
  },
  isLoggedIn: () => sessionStorage.getItem(TOKEN_KEY) !== null,
  uploadResume: (file) => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest("/resumes", { method: "POST", body: form });
  },
  //send saved resume id and optional job description for analysis. Callers pass trimmed text.
  createAnalysis: (resumeId, jobDescription) => {
    const body = {resume_id: resumeId};
    if (jobDescription) { //add job description only when it contains text
      body.job_description = jobDescription;
    }
    return apiRequest("/analyses", {
      method: "POST",
      headers: {"Content-Type": "application/json"} ,
      body: JSON.stringify(body),
    });
  },
};
