import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getJson } from "@/api";
import { useCareer } from "@/lib/career";
import type { AvailabilityStatus, CatalogMetric, Composite, Shortlist, StatsCatalog } from "@/stats/api";

type Ctx = {
  catalog: StatsCatalog | null;
  composites: Composite[];
  shortlists: Shortlist[];
  reloadCatalog: () => Promise<void>;
  reloadComposites: () => Promise<void>;
  reloadShortlists: () => Promise<void>;
  metric: (id: string) => CatalogMetric | undefined;
  label: (viewKey: string) => string;
  unit: (viewKey: string) => string;
  groupLabel: (g: string | null | undefined) => string;
  /** Estado de cada métrica no save atual (vazio enquanto não carregado). */
  availability: Record<string, AvailabilityStatus>;
  usable: (viewKey: string) => boolean;
  reloadAvailability: () => Promise<void>;
};

const C = createContext<Ctx | null>(null);

export function StatsProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<StatsCatalog | null>(null);
  const [composites, setComposites] = useState<Composite[]>([]);
  const [shortlists, setShortlists] = useState<Shortlist[]>([]);
  const [availability, setAvailability] = useState<Record<string, AvailabilityStatus>>({});
  const { career } = useCareer();
  const reloadAvailability = useCallback(async () => {
    if (!career) return setAvailability({});
    const r = await getJson<{ items: { metric: string; status: AvailabilityStatus }[] }>(`/api/stats/availability?career_id=${career.id}`);
    setAvailability(Object.fromEntries(r.items.map((i) => [i.metric, i.status])));
  }, [career]);
  useEffect(() => {
    reloadAvailability().catch(() => setAvailability({}));
  }, [reloadAvailability]);

  const reloadCatalog = useCallback(async () => {
    setCatalog(await getJson<StatsCatalog>("/api/stats/catalog"));
  }, []);
  const reloadComposites = useCallback(async () => {
    setComposites(await getJson<Composite[]>("/api/stats/composites"));
  }, []);
  const reloadShortlists = useCallback(async () => {
    setShortlists(await getJson<Shortlist[]>("/api/stats/shortlists"));
  }, []);

  useEffect(() => {
    reloadCatalog().catch(() => {});
    reloadComposites().catch(() => {});
    reloadShortlists().catch(() => {});
  }, [reloadCatalog, reloadComposites, reloadShortlists]);

  const metricMap = useMemo(() => new Map((catalog?.metrics ?? []).map((m) => [m.id, m])), [catalog]);
  const viewMap = useMemo(() => new Map((catalog?.views ?? []).map((v) => [v.key, v])), [catalog]);
  const groupMap = useMemo(() => new Map((catalog?.groups ?? []).map((g) => [g.key, g.label])), [catalog]);

  const value: Ctx = {
    catalog,
    composites,
    shortlists,
    reloadCatalog,
    reloadComposites,
    reloadShortlists,
    metric: (id) => metricMap.get(id),
    label: (k) => viewMap.get(k)?.label ?? k,
    unit: (k) => viewMap.get(k)?.unit ?? "",
    groupLabel: (g) => (g ? groupMap.get(g) ?? g : "—"),
    availability,
    usable: (k) => ["AVAILABLE", "CALCULABLE", "CUSTOM"].includes(availability[k.split("@")[0]] ?? "AVAILABLE"),
    reloadAvailability,
  };
  return <C.Provider value={value}>{children}</C.Provider>;
}

export function useStats(): Ctx {
  const c = useContext(C);
  if (!c) throw new Error("useStats fora do StatsProvider");
  return c;
}

/** Formata um valor conforme a unidade da vista (contagens inteiras, /90 com 2 casas, % com 1). */
export function fmtStat(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined) return "—";
  if (unit === "percent") return `${v.toFixed(1).replace(".", ",")}%`;
  if (unit.endsWith("/90")) return v.toFixed(2).replace(".", ",");
  if (unit === "minutes" || unit === "matches" || unit === "count")
    return Number.isInteger(v) ? new Intl.NumberFormat("pt-PT").format(v) : v.toFixed(1).replace(".", ",");
  return v.toFixed(2).replace(".", ",");
}
