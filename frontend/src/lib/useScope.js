import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";

// Returns axios config with society_id param when a super-admin is scoped into a society.
export function useScope() {
  const { user, scopeSociety } = useAuth();
  const sid = user?.role === "super_admin" ? scopeSociety : null;
  return { params: sid ? { society_id: sid } : {} };
}

export function useFetch(url, deps = []) {
  const cfg = useScope();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const reload = () => {
    setLoading(true);
    return api.get(url, cfg).then((r) => setData(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { reload(); /* eslint-disable-next-line */ }, deps);
  return { data, loading, reload };
}
