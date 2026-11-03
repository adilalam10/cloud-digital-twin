const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
  } catch {
    throw new Error(`Cannot connect to the backend at ${API}. Start the FastAPI server and try again.`);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status}).`);
  }
  return body;
}

export const api = {
  dashboard: () => request("/api/dashboard"),
  servers: () => request("/api/infrastructure/servers"),
  metrics: () => request("/api/metrics"),
  prediction: () => request("/api/predictions"),
  simulations: () => request("/api/simulations"),
  simulate: (payload) => request("/api/simulate", { method: "POST", body: JSON.stringify(payload) }),
  addServer: (payload) => request("/api/infrastructure/servers", { method: "POST", body: JSON.stringify(payload) }),
  restore: (id) => request(`/api/infrastructure/servers/${id}/restore`, { method: "POST" }),
};
