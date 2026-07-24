import { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=unauth, obj=auth
  const [scopeSociety, setScopeSociety] = useState(
    () => localStorage.getItem("propto_scope") || null
  );

  useEffect(() => {
    const token = localStorage.getItem("propto_token");
    if (!token) {
      setUser(false);
      return;
    }
    api
      .get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => {
        localStorage.removeItem("propto_token");
        setUser(false);
      });
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("propto_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) {}
    localStorage.removeItem("propto_token");
    localStorage.removeItem("propto_scope");
    setUser(false);
    setScopeSociety(null);
  };

  const scopeInto = (societyId) => {
    if (societyId) localStorage.setItem("propto_scope", societyId);
    else localStorage.removeItem("propto_scope");
    setScopeSociety(societyId);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, scopeSociety, scopeInto }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
