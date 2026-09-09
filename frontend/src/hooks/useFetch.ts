import { useCallback, useEffect, useState } from "react";
import api from "../api";

export function useFetch<T>(url: string, params?: Record<string, unknown>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(() => {
    setLoading(true);
    setError("");
    api.get<T>(url, { params })
      .then((r) => setData(r.data))
      .catch(() => setError("Ошибка загрузки"))
      .finally(() => setLoading(false));
  }, [url, JSON.stringify(params)]);

  useEffect(() => { reload(); }, [reload]);

  return { data, loading, error, reload };
}
