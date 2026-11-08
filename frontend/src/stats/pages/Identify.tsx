import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import type { BaseFilters, SearchRequest, SearchResponse, UniverseIn } from "@/stats/api";
import { DEFAULT_UNIVERSE, FiltersForm, UniverseControls } from "@/stats/components";
import { useStats } from "@/stats/context";
import { ResultsTable } from "@/stats/ResultsTable";
import { useStatsQuery } from "@/stats/useStatsQuery";

export default function StatsIdentify() {
  const { career } = useCareer();
  const { composites, label, groupLabel } = useStats();
  const [cid, setCid] = useState<number | null>(null);
  const [minScore, setMinScore] = useState(60);
  const [filters, setFilters] = useState<BaseFilters>({});
  const [universe, setUniverse] = useState<UniverseIn>(DEFAULT_UNIVERSE);
  const [offset, setOffset] = useState(0);
  const comp = composites.find((c) => c.id === cid) ?? composites[0];

  const req: SearchRequest | null = useMemo(() => {
    if (!career || !comp) return null;
    return {
      career_id: career.id, scope: "club", filters: { ...filters, group: comp.group_key }, universe,
      composite_ids: [comp.id], composite_min: { [comp.id]: minScore },
      sort: { by: "composite", composite_id: comp.id, order: "desc" },
      columns: comp.components.slice(0, 5).map((c) => c.metric), limit: 50, offset,
    };
  }, [career, comp, filters, universe, minScore, offset]);
  const { data, error, loading } = useStatsQuery<SearchResponse>(req ? "/api/stats/search" : null, req ?? undefined);

  return (
    <div className="space-y-3">
      <Card className="space-y-3 p-3">
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <div className="col-span-2 space-y-1">
            <Label htmlFor="id-comp">Perfil estatístico (Composite Score)</Label>
            <Select id="id-comp" value={comp?.id ?? ""} onChange={(e) => { setCid(Number(e.target.value)); setOffset(0); }}>
              {composites.map((c) => <option key={c.id} value={c.id}>{c.name} — {c.group_label}</option>)}
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="id-min">Score mínimo</Label>
            <Input id="id-min" type="number" min={0} max={100} value={minScore} onChange={(e) => { setMinScore(Number(e.target.value)); setOffset(0); }} />
          </div>
        </div>
        <FiltersForm value={filters} onChange={(f) => { setFilters(f); setOffset(0); }} showGroup={false} />
        <UniverseControls value={universe} onChange={setUniverse} />
      </Card>
      {comp && (
        <Card>
          <CardHeader><CardTitle>{comp.name}</CardTitle><span className="text-xs text-muted-foreground">{groupLabel(comp.group_key)} · cobertura mínima {Math.round(comp.min_coverage * 100)}%</span></CardHeader>
          <CardContent className="text-sm">
            <p className="text-muted-foreground">Score = média ponderada dos percentis das componentes disponíveis (indicador calculado, não observado).
              Componentes: {comp.components.map((c) => `${label(c.metric)} (${c.weight})`).join(" · ")}. <Link className="text-primary underline" to="/stats/composites">Editar no Composite Score Builder</Link></p>
          </CardContent>
        </Card>
      )}
      {error && <ErrorBox message={error} />}
      {req && <ResultsTable req={req} data={data} loading={loading} onPage={setOffset} source={`Identificação: ${comp?.name}`} />}
      {data && data.total === 0 && (
        <p className="text-sm text-muted-foreground">Sem candidatos. Se as componentes do perfil não existirem neste save, a cobertura fica abaixo do mínimo: veja Metric Availability ou duplique o modelo com uma cobertura mínima menor.</p>
      )}
    </div>
  );
}
