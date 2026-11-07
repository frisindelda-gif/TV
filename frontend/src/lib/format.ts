import type { FieldStatus } from "@/api";

const dateFmt = new Intl.DateTimeFormat("pt-PT", { day: "2-digit", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("pt-PT", { dateStyle: "short", timeStyle: "short" });

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : dateTimeFmt.format(d);
}

/** Dinheiro tal como guardado pela fonte. O FMSuperScout usa GBP; o fmsave a unidade interna do save. */
export function fmtMoney(v: number | null | undefined, currency: string | null = "GBP"): string {
  if (v === null || v === undefined) return "—";
  const sym = currency === "GBP" ? "£" : currency === "EUR" ? "€" : currency === "USD" ? "$" : "";
  const abs = Math.abs(v);
  const s =
    abs >= 1_000_000 ? `${(v / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}M`
    : abs >= 1_000 ? `${(v / 1_000).toFixed(abs >= 100_000 ? 0 : 1)}K`
    : `${v}`;
  return `${sym}${s.replace(".", ",")}`;
}

export function fmtInt(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : new Intl.NumberFormat("pt-PT").format(v);
}

export const STATUS_LABEL: Record<FieldStatus, string> = {
  verified: "verificado",
  unconfirmed: "não confirmado",
  derived: "derivado",
  estimate: "estimativa",
};

export const STATUS_HELP: Record<FieldStatus, string> = {
  verified: "Lido do jogo e confirmado contra o ecrã do FM27 pela ferramenta de origem.",
  unconfirmed: "Lido do jogo, mas o significado ainda não foi confirmado no FM27.",
  derived: "Calculado a partir de valores lidos (p.ex. idade a partir da data de nascimento).",
  estimate: "Estimativa — não é um valor do jogo.",
};

export const CONNECTOR_LABEL: Record<string, string> = {
  live_memory: "Memória (Live)",
  save_file: "Save (.fm)",
  synthetic: "Demonstração",
};

export const FOOT_LABEL: Record<string, string> = { left: "Esquerdo", right: "Direito", both: "Ambos" };

export const COMPETITION_LABEL: Record<string, string> = {
  league: "Liga",
  cup: "Taça",
  continental: "Continental",
  international: "Seleção",
  overall: "Total",
  non_competitive: "Particulares",
  calendar_year_overall: "Ano civil",
  calendar_year_international: "Seleção (ano civil)",
};

/** Classe de cor para atributos 1–20 (escala ao estilo do FM). */
export function attrTone(v: number): string {
  if (v >= 16) return "text-attr-elite";
  if (v >= 11) return "text-attr-good";
  if (v >= 6) return "text-attr-mid";
  return "text-attr-low";
}

/** Classe de fundo para CA/PA 1–200. */
export function abilityTone(v: number | null): string {
  if (v === null) return "bg-muted text-muted-foreground";
  if (v >= 160) return "bg-attr-elite/15 text-attr-elite";
  if (v >= 130) return "bg-attr-good/15 text-attr-good";
  if (v >= 90) return "bg-attr-mid/15 text-attr-mid";
  return "bg-attr-low/15 text-attr-low";
}

/** Nomes legíveis para campos técnicos (estado por campo e cobertura). */
export const FIELD_LABEL: Record<string, string> = {
  ca: "CA",
  pa: "PA",
  pa_range_code: "PA como intervalo",
  attributes: "Atributos",
  personality: "Personalidade",
  positions: "Classificação por posição",
  natural_positions: "Posições naturais",
  accomplished_positions: "Posições competentes",
  age: "Idade",
  birth_date: "Data de nascimento",
  preferred_foot: "Pé preferido",
  market_value: "Valor",
  reputation: "Reputação",
  season_stats: "Estatísticas",
  club: "Clube",
  wage_weekly: "Salário",
  contract_expires: "Fim de contrato",
  personality_complete: "Personalidade completa",
  "contract.wage_weekly": "Salário",
  "contract.expires": "Fim de contrato",
  "contract.loan_listed": "Disponível p/ empréstimo",
};

export const fieldLabel = (k: string) => FIELD_LABEL[k] ?? k;

/** Valor de uma métrica conforme a unidade. */
export function fmtMetric(v: number | null | undefined, unit: string | undefined): string {
  if (v === null || v === undefined) return "—";
  switch (unit) {
    case "pct":
      return `${v.toFixed(1).replace(".", ",")}%`;
    case "per90":
      return v.toFixed(2).replace(".", ",");
    case "rating":
      return v.toFixed(2).replace(".", ",");
    case "minutes":
      return fmtInt(Math.round(v));
    default:
      return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(".", ",");
  }
}

export const METRIC_GROUP_LABEL: Record<string, string> = {
  attack: "Ataque",
  creation: "Criação",
  defence: "Defesa",
  physical: "Físico e disciplina",
  goalkeeping: "Guarda-redes",
  general: "Geral",
};

export function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v > 0 ? `+${v}` : String(v);
}
