import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ErrorBox } from "@/components/common";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import type { BaseFilters, SearchRequest, SearchResponse, SortSpec, UniverseIn } from "@/stats/api";
import { DEFAULT_UNIVERSE, FiltersForm, GroupSelect, MetricSelect, UniverseControls } from "@/stats/components";
import { useStats } from "@/stats/context";
import { ResultsTable, UniverseSummary } from "@/stats/ResultsTable";
import { useStatsQuery } from "@/stats/useStatsQuery";

const PAGE = 50;

export default function StatsRankings() {
  const { career } = useCareer();
  const { catalog, composites, metric, usable, availability } = useStats();
  const [params, setParams] = useSearchParams();
  const group = params.get("group") ?? "CB";
  const [metricKey, setMetricKey] = useState(params.get("metric") ?? "");
  const [sortBy, setSortBy] = useState<SortSpec["by"]>("percentile");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [compositeId, setCompositeId] = useState<number | null>(null);
  const [filters, setFilters] = useState<BaseFilters>({});
  const [universe, setUniverse] = useState<UniverseIn>(DEFAULT_UNIVERSE);
  const [range, setRange] = useState<{ vmin?: number; vmax?: number; pmin?: number; pmax?: number }>({});
  const [offset, setOffset] = useState(0);
  const [scope, setScope] = useState<"club" | "league">("club");

  const groupDef = catalog?.groups.find((g) => g.key === group);
  useEffect(() => {
    if (!groupDef) return;
    const items = groupDef.sections.flatMap((s) => s.items).filter((k) => metric(k.split("@")[0])?.percentile);
    const first = items.find((k) => usable(k)) ?? items[0];
    if (!metricKey || !metric(metricKey.split("@")[0])?.groups.includes(group) || !usable(metricKey)) setMetricKey(first ?? "minutes");
  }, [groupDef, availability]); // eslint-disable-line react-hooks/exhaustive-deps

  const groupComposites = composites.filter((c) => c.group_key === group);
  const req: SearchRequest | null = useMemo(() => {
    if (!career || !metricKey) return null;
    const conds = [];
    if (range.vmin != null || range.vmax != null) conds.push({ metric: metricKey, kind: "value" as const, min: range.vmin, max: range.vmax });
    if (range.pmin != null || range.pmax != null) conds.push({ metric: metricKey, kind: "percentile" as const, min: range.pmin, max: range.pmax });
    return {
      // Só jogadores elegíveis (minutos mínimos do universo), salvo filtro explícito.
      career_id: career.id, scope, filters: { min_minutes: universe.min_minutes, ...filters, group }, universe,
      conditions: conds.length ? { op: "and", conditions: conds } : null,
      sort: sortBy === "composite" ? { by: "composite", composite_id: compositeId ?? groupComposites[0]?.id, order }
        : { by: sortBy, metric: metricKey, order },
      columns: [metricKey, ...(metricKey.endsWith("@p90") || !metric(metricKey)?.per90 ? [] : [`${metricKey}@p90`])],
      composite_ids: groupComposites.map((c) => c.id), limit: PAGE, offset,
    };
  }, [career, metricKey, filters, group, universe, sortBy, order, compositeId, range, offset, scope, groupComposites, metric]);

  const { data, error, loading } = useStatsQuery<SearchResponse>(req ? "/api/stats/search" : null, req ?? undefined);
  const comps = useStatsQuery<{ competitions: string[] }>(career ? `/api/stats/overview?career_id=${career.id}` : null).data?.competitions ?? [];
  const reset = () => setOffset(0);

  return (
    <div className="space-y-3">
      <Card className="space-y-3 p-3">
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
          <div className="space-y-1">
            <Label htmlFor="r-group">Posição</Label>
            <GroupSelect id="r-group" allowAll={false} value={group} onChange={(g) => { setParams({ group: g }); reset(); }} />
          </div>
          <div className="col-span-2 space-y-1">
            <Label>Métrica</Label>
            <MetricSelect value={metricKey} group={group} onlyPercentile onChange={(v) => { setMetricKey(v); reset(); }} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="r-sort">Ordenar por</Label>
            <Select id="r-sort" value={sortBy} onChange={(e) => { setSortBy(e.target.value as SortSpec["by"]); reset(); }}>
              <option value="percentile">Percentil</option>
              <option value="value">Valor (total ou /90)</option>
              <option value="composite" disabled={!groupComposites.length}>Composite Score</option>
              <option value="age">Idade</option>
              <option value="market_value">Valor de mercado</option>
              <option value="wage">Salário</option>
              <option value="minutes">Minutos</option>
            </Select>
          </div>
          {sortBy === "composite" ? (
            <div className="space-y-1">
              <Label htmlFor="r-comp">Composite</Label>
              <Select id="r-comp" value={compositeId ?? groupComposites[0]?.id ?? ""} onChange={(e) => setCompositeId(Number(e.target.value))}>
                {groupComposites.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </div>
          ) : (
            <div className="space-y-1">
              <Label htmlFor="r-order">Ordem</Label>
              <Select id="r-order" value={order} onChange={(e) => setOrder(e.target.value as "asc" | "desc")}>
                <option value="desc">Decrescente</option>
                <option value="asc">Crescente</option>
              </Select>
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="r-scope">Âmbito</Label>
            <Select id="r-scope" value={scope} onChange={(e) => setScope(e.target.value as "club" | "league")}>
              <option value="club">Competições de clube</option>
              <option value="league">Só liga</option>
            </Select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(["vmin", "vmax", "pmin", "pmax"] as const).map((k) => (
            <div key={k} className="space-y-1">
              <Label htmlFor={`r-${k}`}>{{ vmin: "Valor mínimo", vmax: "Valor máximo", pmin: "Percentil mínimo", pmax: "Percentil máximo" }[k]}</Label>
              <Input id={`r-${k}`} type="number" step="any" value={range[k] ?? ""}
                onChange={(e) => { setRange({ ...range, [k]: e.target.value === "" ? undefined : Number(e.target.value) }); reset(); }} />
            </div>
          ))}
        </div>
        <FiltersForm value={filters} onChange={(f) => { setFilters(f); reset(); }} competitions={comps} showGroup={false} />
        <UniverseControls value={universe} onChange={(u) => { setUniverse(u); reset(); }} />
      </Card>
      {error && <ErrorBox message={error} />}
      {req && <ResultsTable req={req} data={data} loading={loading} onPage={setOffset} source={`Rankings ${group}`} />}
      <UniverseSummary data={data} columns={req?.columns ?? []} />
    </div>
  );
}
