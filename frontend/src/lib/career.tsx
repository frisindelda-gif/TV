import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getJson, type AttributeDef, type Career, type MetricsCatalog, type Run } from "@/api";

type Ctx = {
  careers: Career[] | null;
  career: Career | null;
  latestRun: Run | null;
  attributes: AttributeDef[];
  attrLabel: (key: string) => string;
  metrics: MetricsCatalog | null;
  metricDef: (key: string) => MetricsCatalog["metrics"][number] | undefined;
  setCareerId: (id: number) => void;
  reload: () => Promise<void>;
  error: string | null;
};

const CareerContext = createContext<Ctx | null>(null);
const STORAGE_KEY = "fm27si.careerId";

function readStored(): number | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}

export function CareerProvider({ children }: { children: ReactNode }) {
  const [careers, setCareers] = useState<Career[] | null>(null);
  const [careerId, setId] = useState<number | null>(readStored);
  const [latestRun, setLatestRun] = useState<Run | null>(null);
  const [attributes, setAttributes] = useState<AttributeDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<MetricsCatalog | null>(null);

  const reload = useCallback(async () => {
    try {
      const cs = await getJson<Career[]>("/api/careers");
      setCareers(cs);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setCareers([]);
    }
  }, []);

  useEffect(() => {
    void reload();
    getJson<AttributeDef[]>("/api/attributes").then(setAttributes).catch(() => setAttributes([]));
    getJson<MetricsCatalog>("/api/metrics").then(setMetrics).catch(() => setMetrics(null));
  }, [reload]);

  const career = useMemo(() => {
    if (!careers?.length) return null;
    return careers.find((c) => c.id === careerId) ?? [...careers].sort((a, b) => (b.latest_run_id ?? 0) - (a.latest_run_id ?? 0))[0];
  }, [careers, careerId]);

  useEffect(() => {
    if (!career?.latest_run_id) {
      setLatestRun(null);
      return;
    }
    getJson<Run>(`/api/runs/${career.latest_run_id}`).then(setLatestRun).catch(() => setLatestRun(null));
  }, [career?.latest_run_id]);

  const setCareerId = useCallback((id: number) => {
    setId(id);
    try {
      localStorage.setItem(STORAGE_KEY, String(id));
    } catch {
      /* armazenamento indisponível: fica só em memória */
    }
  }, []);

  const attrLabel = useCallback(
    (key: string) => attributes.find((a) => a.key === key)?.label ?? key,
    [attributes],
  );

  const metricDef = useCallback((key: string) => metrics?.metrics.find((m) => m.key === key), [metrics]);

  return (
    <CareerContext.Provider
      value={{ careers, career, latestRun, attributes, attrLabel, metrics, metricDef, setCareerId, reload, error }}
    >
      {children}
    </CareerContext.Provider>
  );
}

export function useCareer(): Ctx {
  const ctx = useContext(CareerContext);
  if (!ctx) throw new Error("useCareer fora do CareerProvider");
  return ctx;
}
