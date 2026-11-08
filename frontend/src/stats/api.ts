// Tipos do Statistical Scouting (espelham backend/fm27si/api_stats.py e stats/queries.py).

export type AvailabilityStatus = "AVAILABLE" | "CALCULABLE" | "PARTIAL" | "UNAVAILABLE" | "INVALID" | "CUSTOM";

export type CatalogMetric = {
  id: string;
  name: string;
  alt_name: string | null;
  description: string;
  category: string;
  category_label: string;
  type: "count" | "percentage" | "ratio" | "derived_count" | "value";
  unit: string;
  per90: boolean;
  percentile: boolean;
  direction: "higher" | "lower";
  composite: boolean;
  composed: boolean;
  builtin: boolean;
  validation_status: string;
  data_source: string;
  eligibility: Record<string, unknown>;
  groups: string[];
  formula_texts: string[];
  source_fields: string[][];
  is_direct: boolean;
};

export type StatsCatalog = {
  version: string;
  scopes: Record<string, string>;
  min_minutes_options: number[];
  metrics: CatalogMetric[];
  groups: { key: string; label: string; positions: string[]; sections: { title: string; items: string[] }[] }[];
  transversal: { title: string; items: string[] }[];
  categories: Record<string, string>;
  tabs: Record<string, { label: string; categories: string[] }>;
  fields: Record<string, { name: string; unit: string; description: string }>;
  views: { key: string; label: string; unit: string }[];
};

export type UniverseIn = {
  competition: "same" | "all";
  position_level: "group" | "position" | "all";
  min_minutes: number;
  min_sample: number;
  shortlist_id?: number | null;
};

export type BaseFilters = Partial<{
  group: string;
  position: string;
  competition: string;
  club: string;
  nationality: string;
  foot: "left" | "right" | "both";
  min_age: number;
  max_age: number;
  min_minutes: number;
  min_value: number;
  max_value: number;
  max_wage: number;
  contract_within_days: number;
  listed: boolean;
  loan_listed: boolean;
  min_potential_gap: number;
  name: string;
}>;

export type Condition = { metric: string; kind: "value" | "percentile"; min?: number | null; max?: number | null };
export type ConditionGroup = { op: "and" | "or"; conditions: (Condition | ConditionGroup)[] };

export type SortSpec = {
  by: "value" | "percentile" | "composite" | "age" | "market_value" | "wage" | "minutes" | "name" | "ca" | "pa";
  metric?: string;
  composite_id?: number;
  order: "asc" | "desc";
};

export type SearchRequest = {
  run_id?: number;
  career_id?: number;
  scope: "club" | "league";
  filters: BaseFilters;
  conditions?: ConditionGroup | null;
  universe: UniverseIn;
  sort: SortSpec;
  columns: string[];
  composite_ids: number[];
  composite_min?: Record<string, number>;
  limit: number;
  offset: number;
};

export type MetricCell = {
  key: string;
  value: number | null;
  total: number | null;
  percentile: number | null;
  rank: number | null;
  universe: number;
  universe_mean: number | null;
  universe_median: number | null;
};

export type StatPlayer = {
  player_id: number;
  snapshot_id: number;
  name: string;
  age: number | null;
  club: string | null;
  competition: string;
  position: string | null;
  group: string | null;
  natural_positions: string[];
  nationalities: string[];
  foot: string | null;
  height: number | null;
  ca: number | null;
  pa: number | null;
  market_value: number | null;
  wage: number | null;
  contract_expires: string | null;
  minutes: number | null;
  listed: boolean;
  loan_listed: boolean;
};

export type SearchItem = StatPlayer & {
  metrics: Record<string, MetricCell>;
  composites: Record<string, { score: number | null; coverage: number | null }>;
};

export type PartitionStats = {
  partition?: string;
  key?: string;
  competition: string;
  position: string;
  eligible: number;
  with_value: number;
  coverage: number | null;
  mean: number | null;
  median: number | null;
  best: number | null;
  worst: number | null;
  sufficient: boolean;
};

export type SearchResponse = {
  run_id: number;
  scope: string;
  scope_label: string;
  total: number;
  items: SearchItem[];
  universe: string;
  universe_summary: Record<string, PartitionStats[]>;
  composites: { id: number; name: string; group: string }[];
  notes: string[];
};

export type Composite = {
  id: number;
  key: string;
  name: string;
  description: string | null;
  builtin: boolean;
  group_key: string;
  group_label: string;
  components: { metric: string; weight: number; invert: boolean }[];
  min_coverage: number;
  updated_at: string;
};

export type Shortlist = { id: number; name: string; players: number; created_at: string };

export type ProfileRow = MetricCell & {
  label: string;
  unit: string;
  metric: string;
  view: "total" | "p90";
  category: string;
  direction: "higher" | "lower";
  type: string;
  composed: boolean;
  status: AvailabilityStatus;
  reason: string;
  source: string;
};

export type StatProfile = {
  player: StatPlayer | null;
  reason?: string;
  group_label: string;
  universe: string;
  scope_label: string;
  overview: ProfileRow[];
  composites: {
    id: number;
    name: string;
    group: string;
    score: number | null;
    coverage: number | null;
    applies: boolean;
    components: { metric: string; label: string; weight: number; percentile: number | null }[];
  }[];
  tabs: Record<string, { label: string; rows: ProfileRow[] }>;
  percentiles: ProfileRow[];
};

export const STATUS_LABEL: Record<AvailabilityStatus, string> = {
  AVAILABLE: "Disponível",
  CALCULABLE: "Calculável",
  PARTIAL: "Parcial",
  UNAVAILABLE: "Indisponível",
  INVALID: "Inválida",
  CUSTOM: "Personalizada",
};
