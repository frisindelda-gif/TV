import { useEffect, useState } from "react";
import { getJson, postJson } from "@/api";

/** Pedido GET/POST com cancelamento e estado de carregamento/erro. */
export function useStatsQuery<T>(url: string | null, body?: unknown, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const key = JSON.stringify(body ?? null);
  useEffect(() => {
    if (!url) return;
    let alive = true;
    setLoading(true);
    const p = body === undefined ? getJson<T>(url) : postJson<T>(url, body);
    p.then((d) => {
      if (alive) {
        setData(d);
        setError(null);
      }
    })
      .catch((e: Error) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [url, key, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading, setData };
}
