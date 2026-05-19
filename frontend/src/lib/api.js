import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("equine_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

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
