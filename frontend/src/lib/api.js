import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const ACCESS_KEY  = "equine_token";
const REFRESH_KEY = "equine_refresh_token";

export const tokens = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: ({ token, refresh_token }) => {
    if (token) localStorage.setItem(ACCESS_KEY, token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = tokens.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Single in-flight refresh promise (deduplicates 401 storms).
let refreshInFlight = null;

const doRefresh = async () => {
  const refresh_token = tokens.getRefresh();
  if (!refresh_token) throw new Error("no_refresh_token");
  const { data } = await axios.post(`${API}/auth/refresh`, { refresh_token });
  tokens.set({ token: data.token, refresh_token: data.refresh_token });
  return data;
};

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error?.config || {};
    const status = error?.response?.status;
    const isAuthEndpoint =
      original.url && (original.url.includes("/auth/login") ||
                       original.url.includes("/auth/refresh") ||
                       original.url.includes("/auth/register"));
    if (status === 401 && !original._retried && !isAuthEndpoint && tokens.getRefresh()) {
      original._retried = true;
      try {
        if (!refreshInFlight) refreshInFlight = doRefresh().finally(() => { refreshInFlight = null; });
        await refreshInFlight;
        const token = tokens.getAccess();
        original.headers = { ...(original.headers || {}), Authorization: `Bearer ${token}` };
        return api(original);
      } catch (refreshErr) {
        tokens.clear();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.assign("/login");
        }
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  },
);

export const fmtDate = (s) => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};
export const fmtTime = (s) => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
};
export const money = (n) => `$${(Number(n) || 0).toLocaleString()}`;

/** Fire-and-forget analytics event. Silently no-ops on failure. */
export const track = (name, props = {}) => {
  api.post("/events", { name, props }).catch(() => {});
};
