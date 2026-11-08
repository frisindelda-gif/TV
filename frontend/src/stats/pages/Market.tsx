import { useMemo, useState } from "react";
import { ErrorBox } from "@/components/common";
import { AbilityPill } from "@/components/common";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { fmtDate, fmtMoney } from "@/lib/format";
import type { BaseFilters, StatPlayer, UniverseIn } from "@/stats/api";
import { AddToShortlist, DEFAULT_UNIVERSE, FiltersForm, MetricSelect, PlayerLink, UniverseControls, posPt } from "@/stats/components";
import { useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

type MarketItem = StatPlayer & { performance: number; value_per_point: number | null; potential_gap: number | null; contract_days: number | null };
type MarketOut = { total: number; items: MarketItem[]; performance_label: string; universe: string; caveat: string; value_per_point_note: string };

export default function StatsMarket() {
  const { career } = useCareer();
  const { composites } = useStats();
  const [mode, setMode] = useState<"composite" | "metric">("composite");
  const [cid, setCid] = useState<number | null>(null);
  const [metric, setMetric] = useState("");
  const [minPerf, setMinPerf] = useState(70);
  const [filters, setFilters] = useState<BaseFilters>({ max_value: 2_000_000 });
  const [status, setStatus] = useState<"" | "listed" | "loan">("");
  const [universe, setUniverse] = useState<UniverseIn>(DEFAULT_UNIVERSE);
  const [sort, setSort] = useState<"performance" | "value" | "value_per_point" | "contract">("performance");
  const comp = composites.find((c) => c.id === cid) ?? composites[0];

  const body = useMemo(() => {
    if (!career) return null;
    if (mode === "metric" && !metric) return null;
    if (mode === "composite" && !comp) return null; // composites ainda a carregar
    const f: BaseFilters = { ...filters };
    if (mode === "composite" && comp) f.group = comp.group_key;
    if (status === "listed") f.listed = true;
    if (status === "loan") f.loan_listed = true;
    return { career_id: career.id, filters: f, universe, min_performance: minPerf, sort, limit: 100,
      ...(mode === "composite" ? { composite_id: comp?.id } : { metric }) };
  }, [career, mode, metric, comp, filters, status, universe, minPerf, sort]);
  const { data, error, loading } = useStatsQuery<MarketOut>(body ? "/api/stats/market" : null, body ?? undefined);

  return (
    <div className="space-y-3">
      <Card className="space-y-3 p-3">
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
          <div className="space-y-1"><Label htmlFor="mk-mode">Desempenho por</Label>
            <Select id="mk-mode" value={mode} onChange={(e) => setMode(e.target.value as "composite" | "metric")}>
              <option value="composite">Composite Score</option><option value="metric">Percentil de uma métrica</option>
            </Select></div>
          <div className="col-span-2 space-y-1"><Label>{mode === "composite" ? "Perfil" : "Métrica"}</Label>
            {mode === "composite" ? (
              <Select aria-label="Perfil" value={comp?.id ?? ""} onChange={(e) => setCid(Number(e.target.value))}>
                {composites.map((c) => <option key={c.id} value={c.id}>{c.name} — {c.group_label}</option>)}
              </Select>
            ) : <MetricSelect value={metric} group={filters.group} onlyPercentile onChange={setMetric} />}</div>
          <div className="space-y-1"><Label htmlFor="mk-min">Desempenho mínimo</Label>
            <Input id="mk-min" type="number" min={0} max={100} value={minPerf} onChange={(e) => setMinPerf(Number(e.target.value))} /></div>
          <div className="space-y-1"><Label htmlFor="mk-status">Situação</Label>
            <Select id="mk-status" value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
              <option value="">Qualquer</option><option value="listed">Transferível</option><option value="loan">Emprestável</option>
            </Select></div>
          <div className="space-y-1"><Label htmlFor="mk-sort">Ordenar por</Label>
            <Select id="mk-sort" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
              <option value="performance">Desempenho</option><option value="value">Valor mais baixo</option>
              <option value="value_per_point">Valor por ponto de desempenho</option><option value="contract">Contrato a acabar primeiro</option>
            </Select></div>
        </div>
        <FiltersForm value={filters} onChange={setFilters} showGroup={mode === "metric"} />
        <UniverseControls value={universe} onChange={setUniverse} />
      </Card>
      {error && <ErrorBox message={error} />}
      {data && (
        <>
          <div className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">{data.caveat}</div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="text-muted-foreground">{data.total} oportunidades · {data.performance_label} · {data.universe}</span>
            <AddToShortlist playerIds={data.items.map((i) => i.player_id)} source="Market Opportunities" />
          </div>
          <Card className={loading ? "overflow-x-auto opacity-60" : "overflow-x-auto"}>
            <table className="w-full min-w-[900px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground"><tr>
                <th className="py-2 pl-3 font-medium">Jogador</th><th className="font-medium">Pos.</th><th className="font-medium">Clube</th>
                <th className="text-right font-medium">Desempenho</th><th className="text-right font-medium">Valor</th><th className="text-right font-medium">Salário</th>
                <th className="text-right font-medium" title={data.value_per_point_note}>£/ponto</th><th className="font-medium">Contrato</th>
                <th className="text-center font-medium">CA/PA</th><th className="font-medium">Situação</th></tr></thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.player_id} className="border-b last:border-0">
                    <td className="py-1.5 pl-3"><PlayerLink id={p.player_id} name={p.name} /> <span className="text-xs text-muted-foreground">{p.age}</span></td>
                    <td className="text-xs">{posPt(p.position)}</td><td className="max-w-[180px] truncate">{p.club}</td>
                    <td className="text-right font-semibold tabular-nums">{Math.round(p.performance)}</td>
                    <td className="text-right tabular-nums">{fmtMoney(p.market_value)}</td><td className="text-right tabular-nums">{fmtMoney(p.wage)}</td>
                    <td className="text-right tabular-nums">{fmtMoney(p.value_per_point)}</td>
                    <td className="text-xs">{fmtDate(p.contract_expires)}</td>
                    <td className="whitespace-nowrap text-center"><AbilityPill value={p.ca} /> <AbilityPill value={p.pa} /></td>
                    <td className="text-xs">{[p.listed && "transferível", p.loan_listed && "emprestável"].filter(Boolean).join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.items.length === 0 && <div className="p-6 text-center text-sm text-muted-foreground">Nenhuma oportunidade com estes critérios.</div>}
          </Card>
        </>
      )}
    </div>
  );
}
