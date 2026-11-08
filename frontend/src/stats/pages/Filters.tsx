import { Plus, Save, Search, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { deleteJson, getJson, postJson } from "@/api";
import { ErrorBox } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import type { BaseFilters, Condition, ConditionGroup, SearchRequest, SearchResponse, UniverseIn } from "@/stats/api";
import { DEFAULT_UNIVERSE, FiltersForm, MetricSelect, UniverseControls } from "@/stats/components";
import { ResultsTable, UniverseSummary } from "@/stats/ResultsTable";

type Saved = { id: number; name: string; kind: string; definition: Partial<SearchRequest>; created_at: string };

const isGroup = (c: Condition | ConditionGroup): c is ConditionGroup => "conditions" in c;
const newCond = (): Condition => ({ metric: "", kind: "value", min: null, max: null });

/** Exemplos do pedido, prontos a usar. */
const EXAMPLES: { name: string; filters: BaseFilters; conditions: ConditionGroup }[] = [
  {
    name: "Centrais: recuperação, jogo aéreo e passe (≤ 23 anos)",
    filters: { group: "CB", max_age: 22, min_minutes: 900 },
    conditions: { op: "and", conditions: [
      { metric: "recoveries@p90", kind: "value", min: 8 },
      { metric: "aerial_duel_pct", kind: "percentile", min: 75 },
      { metric: "pass_pct", kind: "value", min: 85 },
    ] },
  },
  {
    name: "Extremos: drible, criação e contribuições (≤ 21 anos)",
    filters: { group: "W", max_age: 20 },
    conditions: { op: "and", conditions: [
      { metric: "dribbles_completed@p90", kind: "value", min: 2 },
      { metric: "chances_created", kind: "percentile", min: 80 },
      { metric: "goal_contributions@p90", kind: "value", min: 1 },
    ] },
  },
];

function collectMetrics(g: ConditionGroup): string[] {
  return g.conditions.flatMap((c) => (isGroup(c) ? collectMetrics(c) : c.metric ? [c.metric] : []));
}

export default function StatsFilters() {
  const { career } = useCareer();
  const [filters, setFilters] = useState<BaseFilters>({ min_minutes: 450 });
  const [conds, setConds] = useState<ConditionGroup>({ op: "and", conditions: [newCond()] });
  const [universe, setUniverse] = useState<UniverseIn>(DEFAULT_UNIVERSE);
  const [req, setReq] = useState<SearchRequest | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<Saved[]>([]);

  const loadSaved = () => getJson<Saved[]>("/api/stats/searches?kind=filter").then(setSaved).catch(() => {});
  useEffect(() => void loadSaved(), []);

  const build = (offset = 0): SearchRequest | null => {
    if (!career) return null;
    const metrics = Array.from(new Set(collectMetrics(conds)));
    const clean = (g: ConditionGroup): ConditionGroup => ({
      op: g.op,
      conditions: g.conditions.map((c) => (isGroup(c) ? clean(c) : c)).filter((c) => (isGroup(c) ? c.conditions.length : c.metric)),
    });
    return {
      career_id: career.id, scope: "club", filters, universe, conditions: clean(conds),
      sort: metrics[0] ? { by: "percentile", metric: metrics[0], order: "desc" } : { by: "minutes", order: "desc" },
      columns: metrics.length ? metrics : ["minutes"], composite_ids: [], limit: 50, offset,
    };
  };

  const run = async (r: SearchRequest | null) => {
    if (!r) return;
    setReq(r);
    setLoading(true);
    try {
      setData(await postJson<SearchResponse>("/api/stats/search", r));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    const r = build();
    const name = window.prompt("Nome da pesquisa");
    if (!r || !name) return;
    const { career_id: _c, offset: _o, ...definition } = r;
    await postJson("/api/stats/searches", { name, kind: "filter", definition });
    await loadSaved();
  };

  const load = (d: Partial<SearchRequest>) => {
    setFilters(d.filters ?? {});
    setConds(d.conditions ?? { op: "and", conditions: [newCond()] });
    setUniverse(d.universe ?? DEFAULT_UNIVERSE);
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
      <div className="min-w-0 space-y-3">
        <Card>
          <CardHeader><CardTitle>Condições estatísticas</CardTitle>
            <span className="text-xs text-muted-foreground">dados em falta nunca cumprem uma condição</span></CardHeader>
          <CardContent>
            <GroupEditor g={conds} onChange={setConds} depth={0} group={filters.group} />
          </CardContent>
        </Card>
        <Card className="space-y-3 p-3">
          <FiltersForm value={filters} onChange={setFilters} />
          <UniverseControls value={universe} onChange={setUniverse} />
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void run(build())}><Search /> Pesquisar</Button>
            <Button variant="outline" onClick={() => void save()}><Save /> Guardar pesquisa</Button>
          </div>
        </Card>
        {error && <ErrorBox message={error} />}
        {req && <ResultsTable req={req} data={data} loading={loading} onPage={(o) => void run({ ...req, offset: o })} source="Advanced Filters" />}
        {req && <UniverseSummary data={data} columns={req.columns} />}
      </div>
      <aside className="space-y-3">
        <Card>
          <CardHeader><CardTitle>Exemplos</CardTitle></CardHeader>
          <CardContent className="space-y-1.5">
            {EXAMPLES.map((ex) => (
              <button key={ex.name} type="button" className="block w-full rounded-md border px-2 py-1.5 text-left text-xs hover:bg-muted"
                onClick={() => { setFilters(ex.filters); setConds(ex.conditions); }}>
                {ex.name}
              </button>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Pesquisas guardadas</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            {saved.length === 0 && <p className="text-xs text-muted-foreground">Nenhuma.</p>}
            {saved.map((s) => (
              <div key={s.id} className="flex items-center gap-1">
                <button type="button" className="min-w-0 flex-1 truncate rounded px-1 py-1 text-left text-sm hover:bg-muted" onClick={() => load(s.definition)}>
                  {s.name}
                </button>
                <Button variant="ghost" size="icon" aria-label="Apagar pesquisa" onClick={() => void deleteJson(`/api/stats/searches/${s.id}`).then(loadSaved)}>
                  <Trash2 />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
        <p className="text-xs text-muted-foreground">
          Cada pesquisa é um JSON validado pelo backend; está preparado para, no futuro, ser gerado a partir de linguagem natural.
        </p>
      </aside>
    </div>
  );
}

function GroupEditor({ g, onChange, depth, group }: { g: ConditionGroup; onChange: (g: ConditionGroup) => void; depth: number; group?: string }) {
  const set = (i: number, c: Condition | ConditionGroup) => onChange({ ...g, conditions: g.conditions.map((x, j) => (j === i ? c : x)) });
  const remove = (i: number) => onChange({ ...g, conditions: g.conditions.filter((_, j) => j !== i) });
  return (
    <div className={depth ? "rounded-md border border-dashed p-2" : ""}>
      <div className="mb-2 flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Cumprir</span>
        <Select aria-label="Operador" className="h-8 w-auto" value={g.op} onChange={(e) => onChange({ ...g, op: e.target.value as "and" | "or" })}>
          <option value="and">todas (E)</option>
          <option value="or">pelo menos uma (OU)</option>
        </Select>
        <span className="text-muted-foreground">das condições:</span>
      </div>
      <div className="space-y-2">
        {g.conditions.map((c, i) =>
          isGroup(c) ? (
            <div key={i} className="flex gap-1">
              <div className="flex-1"><GroupEditor g={c} onChange={(x) => set(i, x)} depth={depth + 1} group={group} /></div>
              <Button variant="ghost" size="icon" aria-label="Remover grupo" onClick={() => remove(i)}><X /></Button>
            </div>
          ) : (
            <div key={i} className="grid grid-cols-[minmax(0,1fr)_auto] gap-1 sm:grid-cols-[minmax(0,2fr)_140px_90px_90px_auto]">
              <MetricSelect value={c.metric} group={group} onChange={(v) => set(i, { ...c, metric: v })} className="col-span-2 sm:col-span-1" />
              <Select aria-label="Tipo" value={c.kind} onChange={(e) => set(i, { ...c, kind: e.target.value as Condition["kind"] })}>
                <option value="value">Valor</option>
                <option value="percentile">Percentil</option>
              </Select>
              <Input aria-label="Mínimo" placeholder="mín." type="number" step="any" value={c.min ?? ""}
                onChange={(e) => set(i, { ...c, min: e.target.value === "" ? null : Number(e.target.value) })} />
              <Input aria-label="Máximo" placeholder="máx." type="number" step="any" value={c.max ?? ""}
                onChange={(e) => set(i, { ...c, max: e.target.value === "" ? null : Number(e.target.value) })} />
              <Button variant="ghost" size="icon" aria-label="Remover condição" onClick={() => remove(i)}><X /></Button>
            </div>
          ),
        )}
      </div>
      <div className="mt-2 flex gap-2">
        <Button size="sm" variant="outline" onClick={() => onChange({ ...g, conditions: [...g.conditions, newCond()] })}><Plus /> Condição</Button>
        {depth < 2 && (
          <Button size="sm" variant="outline" onClick={() => onChange({ ...g, conditions: [...g.conditions, { op: "or", conditions: [newCond()] }] })}>
            <Plus /> Grupo {g.op === "and" ? "OU" : "E"}
          </Button>
        )}
      </div>
    </div>
  );
}
