import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, tokens } from "../lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const access = tokens.getAccess();
    if (!access) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    tokens.set({ token: data.token, refresh_token: data.refresh_token });
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refresh_token = tokens.getRefresh();
    if (refresh_token) {
      try {
        await api.post("/auth/logout", { refresh_token });
      } catch (err) {
        console.warn("[auth] logout request failed; clearing local session anyway", err);
      }
    }
    tokens.clear();
    setUser(null);
  }, []);

  const setSession = useCallback((newUser) => setUser(newUser), []);

  const value = useMemo(
    () => ({ user, login, logout, loading, setSession }),
    [user, login, logout, loading, setSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
