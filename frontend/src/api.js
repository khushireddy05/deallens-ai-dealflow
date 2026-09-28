const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// FastAPI returns either a string or a list of {loc, msg} objects as `detail`.
export function formatDetail(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg ?? JSON.stringify(d)).join("; ") || fallback;
  }
  return fallback;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${BASE}. Is the backend running?`);
  }
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(response.status, formatDetail(detail, response.statusText));
  }
  return response.json();
}

function query(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  listOpportunities: (params) => request(`/opportunities${query(params)}`),
  getOpportunity: (id) => request(`/opportunities/${id}`),
  submitPitch: (pitch) =>
    request("/opportunities", { method: "POST", body: JSON.stringify(pitch) }),
  setStatus: (id, status) =>
    request(`/opportunities/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  retry: (id) => request(`/opportunities/${id}/retry`, { method: "POST" }),
  listFailures: () => request("/failures"),
  listCompanies: (params) => request(`/companies${query(params)}`),
  samples: () => request("/samples"),
  thesis: () => request("/thesis"),
};
