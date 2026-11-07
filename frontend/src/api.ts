// Cliente da API local. Tipos espelham backend/fm27si/api.py.

export type FieldStatus = "verified" | "unconfirmed" | "derived" | "estimate";
export type Quality = "ok" | "warning" | "error";
export type Category = "technical" | "mental" | "physical" | "goalkeeping" | "hidden" | "personality";

export type AttributeDef = { key: string; label: string; category: Category };

export type Career = {
  id: number;
  key: string;
  label: string;
  game: string | null;
  manager_name: string | null;
  runs: number;
  latest_run_id: number | null;
};

export type Run = {
  id: number;
  career_id: number;
  connector: "live_memory" | "save_file" | "synthetic";
  tool: string;
  source_path: string | null;
  source_sha256: string | null;
  read_at: string;
  imported_at: string;
  game: string | null;
  game_version: string | null;
  game_version_supported: boolean | null;
  game_date: string | null;
  game_date_status: FieldStatus;
  season_label: string | null;
  managed_club: string | null;
  currency: string | null;
  synthetic: boolean;
  player_count: number;
  source_player_count: number;
  error_count: number;
  warning_count: number;
  unavailable_fields: string[];
  warnings: string[];
};

export type PlayerRow = {
  player_id: number;
  unique_id: number | null;
  name: string;
  age: number | null;
  ca: number | null;
  pa: number | null;
  club: string | null;
  nationalities: string[];
  positions: string[];
  natural_positions: string[];
  market_value: number | null;
  wage_weekly: number | null;
  contract_expires: string | null;
  quality: Quality;
  ca_delta: number | null;
  is_new: boolean | null;
  position_group: string | null;
  minutes: number | null;
  metric_key: string | null;
  metric_value: number | null;
  best_position: string | null;
  best_position_score: number | null;
  best_role: string | null;
  best_role_score: number | null;
};

export type MetricDef = {
  key: string;
  label: string;
  group: "attack" | "creation" | "defence" | "physical" | "goalkeeping" | "general";
  unit: "per90" | "pct" | "total" | "rating" | "minutes";
  higher_is_better: boolean;
  gk_only: boolean;
  outfield_only: boolean;
};

export type MetricsCatalog = {
  metrics: MetricDef[];
  position_groups: Record<string, string>;
  radar: Record<string, string[]>;
  min_minutes_for_percentile: number;
};

export type PlayerMetrics = {
  position_group: string | null;
  position_group_label: string | null;
  minutes: number;
  appearances: number;
  values: Record<string, number | null>;
  percentiles: Record<string, number>;
  peers: number | null;
  min_minutes: number;
  enough_minutes: boolean;
  radar: string[];
  status: FieldStatus;
};

export type OverviewPlayer = {
  player_id: number;
  name: string;
  age: number | null;
  club: string | null;
  ca: number | null;
  pa: number | null;
  ca_delta: number | null;
  position_group: string | null;
  positions: string[];
  metric: number | null;
  minutes: number | null;
};

export type Overview = {
  run_id: number;
  game_date: string | null;
  season_label: string | null;
  synthetic: boolean;
  kpis: Record<"players" | "avg_ca" | "elite" | "wonderkids" | "new_players" | "new_regens" | "risers" | "fallers" | "with_stats", number>;
  has_growth: boolean;
  has_metrics: boolean;
  ca_histogram: { from: number; to: number; players: number }[];
  pa_histogram: { from: number; to: number; players: number }[];
  position_groups: { group: string | null; label: string; players: number; avg_ca: number; max_ca: number | null }[];
  clubs: { name: string; players: number; avg_ca: number; max_pa: number | null }[];
  top_risers: OverviewPlayer[];
  top_new_regens: OverviewPlayer[];
  top_prospects: OverviewPlayer[];
  top_rated: OverviewPlayer[];
  top_scorers: OverviewPlayer[];
};

export type PlayerPage = { run_id: number; total: number; items: PlayerRow[] };

export type SeasonStat = {
  season: string | null;
  competition_kind: string;
  club_name: string | null;
  starts: number | null;
  sub_appearances: number | null;
  minutes: number | null;
  goals: number | null;
  assists: number | null;
  average_rating: number | null;
  player_of_the_match: number | null;
  expected_goals: number | null;
  expected_assists: number | null;
  yellow_cards: number | null;
  red_cards: number | null;
  clean_sheets: number | null;
};

export type HistoryPoint = {
  run_id: number;
  connector: string;
  game_date: string | null;
  read_at: string;
  ca: number | null;
  pa: number | null;
  market_value: number | null;
  club: string | null;
};

export type Contract = {
  wage_weekly: number | null;
  start: string | null;
  expires: string | null;
  squad_status: string | null;
  transfer_listed: boolean | null;
  loan_listed: boolean | null;
  not_for_sale: boolean | null;
  set_for_release: boolean | null;
  on_loan: boolean | null;
  loan_parent_club: string | null;
  loan_end: string | null;
};

export type Profile = {
  player_id: number;
  unique_id: number | null;
  name: string;
  birth_date: string | null;
  birth_year: number | null;
  gender: string | null;
  nationalities: string[];
  age: number | null;
  height_cm: number | null;
  foot: { left: number | null; right: number | null; preferred: string | null };
  ability: { ca: number | null; pa: number | null; pa_range_code: number | null };
  reputation: { home: number | null; current: number | null; world: number | null };
  club: { id: number | null; name: string | null; division: string | null };
  contract: Contract | null;
  market_value: number | null;
  positions: { ratings: Record<string, number>; natural: string[]; accomplished: string[] };
  roles: string[];
  traits: string[];
  attributes: Partial<Record<Category, Record<string, number>>>;
  season_stats: SeasonStat[];
  quality: Quality;
  growth: { ca_delta: number | null; pa_delta: number | null; is_new: boolean | null; ca_since_first: number | null };
  metrics: PlayerMetrics | null;
  issues: { severity: "error" | "warning"; field: string; code: string; message: string; value: unknown }[];
  field_status: Record<string, FieldStatus>;
  provenance: {
    run_id: number;
    connector: string;
    tool: string;
    source_path: string | null;
    source_sha256: string | null;
    read_at: string;
    imported_at: string;
    game_date: string | null;
    game_date_status: FieldStatus;
    game_version: string | null;
    synthetic: boolean;
    currency: string | null;
  };
  unavailable_fields: string[];
  history: HistoryPoint[];
};

export type FilterOptions = {
  run_id: number;
  game_date: string | null;
  clubs: { name: string; players: number }[];
  nationalities: { name: string; players: number }[];
  positions: string[];
};

export type Integrity = {
  run_id: number;
  ok: boolean;
  checks: { name: string; ok: boolean; detail: unknown }[];
  quality: Record<string, number>;
  issues_by_field_code: Record<string, number>;
  coverage: Record<string, number | null>;
};

export type ImportOut = {
  duplicate: boolean;
  created_players: number;
  updated_players: number;
  skipped: number;
  run: Run;
  warnings: string[];
};

async function handle<T>(r: Response): Promise<T> {
  return handleResponse<T>(r);
}

async function handleResponse<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const body = await r.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail))
        msg = body.detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).join(".")}: ${d.msg}`).join(" · ");
      else msg = JSON.stringify(body.detail ?? body);
    } catch {
      msg = `${r.status} ${r.statusText}`;
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  return fetch(url, { signal }).then((r) => handle<T>(r));
}

export function postJson<T>(url: string, body?: unknown): Promise<T> {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

// ------------------------------------------------------------- avaliação
export type Confidence = "high" | "medium" | "low";
export type MetricCategory = "technical" | "mental" | "physical" | "tactical" | "position_specific";

export type SpecAttributeWeight = { attribute: string; weight: number; invert: boolean };
export type SpecMetricWeight = { metric: string; weight: number };
export type SpecMetric = {
  key: string;
  name: string;
  description: string;
  category: MetricCategory;
  positions: string[];
  attributes: SpecAttributeWeight[];
};
export type SpecPosition = { key: string; metrics: SpecMetricWeight[] };
export type SpecRole = {
  key: string;
  name: string;
  description: string;
  positions: string[];
  metrics: SpecMetricWeight[];
  enabled: boolean;
  availability: "confirmed" | "unconfirmed";
};
export type EvaluationSpec = {
  schema_version: 1;
  min_coverage: number;
  metrics: SpecMetric[];
  positions: SpecPosition[];
  roles: SpecRole[];
};

export type EvalModel = {
  id: number;
  key: string;
  name: string;
  description: string | null;
  builtin: boolean;
  active: boolean;
  base_key: string | null;
  spec_hash: string;
  created_at: string;
  updated_at: string;
  modified_from_original: boolean;
};
export type EvalModelFull = EvalModel & {
  spec: EvaluationSpec;
  metrics: (SpecMetric & { formula: string; used_by_positions: string[]; used_by_roles: string[]; category_label: string })[];
};

export type EvalCatalog = {
  positions: { key: string; pt: string; name: string }[];
  ranking_groups: { key: string; label: string; positions: string[] }[];
  categories: Record<MetricCategory, string>;
  attributes: AttributeDef[];
  scale: string;
};

export type ScoreItem = { key: string; name: string; score: number | null; coverage: number; confidence: Confidence };
export type MetricResult = ScoreItem & {
  category: MetricCategory;
  attributes: { attribute: string; value: number; normalized: number; weight: number; invert: boolean }[];
  missing: string[];
};

export type RankedNeighbour = { player_id: number; name: string; age: number | null; club: string | null; ca: number | null; pa: number | null; score: number };

export type PlayerEvaluation = {
  model: { id: number; name: string; spec_hash: string; builtin: boolean };
  data_status: FieldStatus | null;
  eligible_positions: string[];
  focus: string | null;
  positions: (ScoreItem & { pt: string; eligible: boolean; familiarity: number | null; position_mean: number | null })[];
  roles: (ScoreItem & { positions: string[]; availability: string; eligible: boolean })[];
  metrics: MetricResult[];
  comparison: { metric: string; name: string; category: MetricCategory; weight_share: number; score: number | null; position_mean: number | null; diff: number | null; coverage: number }[];
  position_mean_score: number | null;
  position_players: number;
  attributes_vs_position: { attribute: string; label: string; value: number | null; position_mean: number | null }[];
  strengths: PlayerEvaluation["comparison"];
  weaknesses: PlayerEvaluation["comparison"];
  ranking: {
    position: string;
    rank: number;
    of: number;
    percentile: number | null;
    above: RankedNeighbour[];
    below: RankedNeighbour[];
    top: RankedNeighbour[];
  } | null;
  stored_state: "fresh" | "stale" | null;
};

export type RankingItem = {
  rank: number;
  player_id: number;
  name: string;
  age: number | null;
  club: string | null;
  nationalities: string[];
  positions: string[];
  natural_positions: string[];
  ca: number | null;
  pa: number | null;
  ca_delta: number | null;
  market_value: number | null;
  score: number | null;
  group_positions: Record<string, number | null>;
  best_position: string | null;
  best_role: string | null;
  best_role_score: number | null;
  role_scores: Record<string, number>;
  confidence: Confidence;
  incomplete: boolean;
};

export type Rankings = {
  run_id: number;
  model: { id: number; name: string; spec_hash: string };
  group: string;
  label: string;
  positions: string[];
  total: number;
  items: RankingItem[];
  state: "fresh" | "stale" | "missing";
};

export function putJson<T>(url: string, body: unknown): Promise<T> {
  return fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) =>
    handleResponse<T>(r),
  );
}

export function deleteJson<T>(url: string): Promise<T> {
  return fetch(url, { method: "DELETE" }).then((r) => handleResponse<T>(r));
}
