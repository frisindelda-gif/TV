import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getJson, type Confidence, type EvalCatalog, type EvalModel, type EvalModelFull } from "@/api";
import { POSITION_LABEL } from "@/components/PositionPitch";

type Ctx = {
  catalog: EvalCatalog | null;
  active: EvalModelFull | null;
  models: EvalModel[];
  reload: () => Promise<void>;
  posPt: (key: string) => string;
  posName: (key: string) => string;
  roleName: (key: string) => string;
  metricName: (key: string) => string;
};

const EvalContext = createContext<Ctx | null>(null);

export function EvaluationProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<EvalCatalog | null>(null);
  const [active, setActive] = useState<EvalModelFull | null>(null);
  const [models, setModels] = useState<EvalModel[]>([]);

  const reload = useCallback(async () => {
    try {
      const ms = await getJson<EvalModel[]>("/api/evaluation/models");
      setModels(ms);
      const a = ms.find((m) => m.active) ?? ms[0];
      if (a) setActive(await getJson<EvalModelFull>(`/api/evaluation/models/${a.id}`));
    } catch {
      setModels([]);
    }
  }, []);

  useEffect(() => {
    getJson<EvalCatalog>("/api/evaluation/catalog").then(setCatalog).catch(() => setCatalog(null));
    void reload();
  }, [reload]);

  const posPt = useCallback((k: string) => catalog?.positions.find((p) => p.key === k)?.pt ?? POSITION_LABEL[k] ?? k, [catalog]);
  const posName = useCallback((k: string) => catalog?.positions.find((p) => p.key === k)?.name ?? k, [catalog]);
  const roleName = useCallback((k: string) => active?.spec.roles.find((r) => r.key === k)?.name ?? k, [active]);
  const metricName = useCallback((k: string) => active?.spec.metrics.find((m) => m.key === k)?.name ?? k, [active]);

  return (
    <EvalContext.Provider value={{ catalog, active, models, reload, posPt, posName, roleName, metricName }}>
      {children}
    </EvalContext.Provider>
  );
}

export function useEvaluation(): Ctx {
  const c = useContext(EvalContext);
  if (!c) throw new Error("useEvaluation fora do EvaluationProvider");
  return c;
}

/** Cor do texto para uma pontuação 0–100 (mesma lógica de bandas dos atributos). */
export function scoreTone(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-muted-foreground";
  if (v >= 80) return "text-attr-elite";
  if (v >= 65) return "text-attr-good";
  if (v >= 50) return "text-attr-mid";
  return "text-attr-low";
}

export const CONFIDENCE_LABEL: Record<Confidence, string> = { high: "alta", medium: "média", low: "baixa" };
export const CONFIDENCE_HELP: Record<Confidence, string> = {
  high: "Todos os atributos presentes e verificados no jogo.",
  medium: "Faltam alguns atributos ou os atributos ainda não foram confirmados no FM27.",
  low: "Faltam muitos atributos ou os dados são estimados/fictícios.",
};

export const CATEGORY_ORDER = ["technical", "mental", "physical", "tactical", "position_specific"] as const;
