import { Plus, X } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getJson, type PlayerPage } from "@/api";
import { AbilityPill, ErrorBox } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { fmtDate, fmtMoney } from "@/lib/format";
import type { MetricCell, StatPlayer, UniverseIn } from "@/stats/api";
import { DEFAULT_UNIVERSE, MetricSelect, Notes, PctCell, PlayerLink, UniverseControls, posPt } from "@/stats/components";
import { fmtStat, useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

const SERIES = ["hsl(var(--chart-1))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))"];
const DASH = ["", "6 3", "2 2", "8 3 2 3"]; // codificação secundária (não só cor)
type CmpPlayer = StatPlayer & { metrics: Record<string, MetricCell>; composites: Record<string, { score: number | null; coverage: number | null }> };
type CmpOut = { players: CmpPlayer[]; metrics: { key: string; label: string; unit: string; direction: string }[];
  composites: { id: number; name: string; group: string }[]; universe: string; warnings: string[] };

export default function StatsCompare() {
  const { career } = useCareer();
  const { catalog, label } = useStats();
  const [players, setPlayers] = useState<{ id: number; name: string }[]>([]);
  const [metrics, setMetrics] = useState<string[]>(["goals@p90", "assists@p90", "key_passes@p90", "pass_pct", "dribbles_completed@p90", "tackles_won@p90", "interceptions@p90", "aerial_duel_pct"]);
  const [universe, setUniverse] = useState<UniverseIn>(DEFAULT_UNIVERSE);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlayerPage["items"]>([]);
  const [tab, setTab] = useState("");

  const body = useMemo(() => (career && players.length ? { career_id: career.id, player_ids: players.map((p) => p.id), metrics, universe } : null),
    [career, players, metrics, universe]);
  const { data, error } = useStatsQuery<CmpOut>(body ? "/api/stats/compare" : null, body ?? undefined);

  const search = (v: string) => {
    setQ(v);
    if (!career || v.length < 2) return setHits([]);
    getJson<PlayerPage>(`/api/players?career_id=${career.id}&q=${encodeURIComponent(v)}&limit=8`).then((p) => setHits(p.items)).catch(() => {});
  };
  const applyTab = (t: string) => {
    setTab(t);
    if (!catalog || !t) return;
    const cats = catalog.tabs[t].categories;
    const keys = catalog.views.filter((v) => cats.includes(catalog.metrics.find((m) => m.id === v.key.split("@")[0])?.category ?? "")
      && (v.key.endsWith("@p90") || !catalog.metrics.find((m) => m.id === v.key)?.per90)).map((v) => v.key);
    setMetrics(keys.slice(0, 12));
  };
  const chartRows = data?.metrics.map((m) => {
    const row: Record<string, string | number | null> = { label: m.label.replace(" por 90 minutos", " /90") };
    data.players.forEach((p, i) => { row[`p${i}`] = p.metrics[m.key]?.percentile ?? null; });
    return row;
  }) ?? [];

  return (
    <div className="space-y-3">
      <Card className="space-y-3 p-3">
        <div className="flex flex-wrap items-end gap-2">
          {players.map((p, i) => (
            <span key={p.id} className="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-sm" style={{ borderColor: SERIES[i] }}>
              <span className="size-2.5 rounded-full" style={{ background: SERIES[i] }} /> {p.name}
              <button type="button" aria-label={`Remover ${p.name}`} onClick={() => setPlayers(players.filter((x) => x.id !== p.id))}><X className="size-3" /></button>
            </span>
          ))}
          {players.length < 4 && (
            <div className="relative w-64 space-y-1">
              <Label htmlFor="cmp-q">Adicionar jogador ({players.length}/4)</Label>
              <Input id="cmp-q" value={q} placeholder="Procurar…" onChange={(e) => search(e.target.value)} />
              {hits.length > 0 && (
                <ul className="absolute z-10 mt-1 w-full rounded-md border bg-card shadow">
                  {hits.map((h) => (
                    <li key={h.player_id}><button type="button" className="w-full px-2 py-1 text-left text-sm hover:bg-muted"
                      onClick={() => { if (!players.some((p) => p.id === h.player_id)) setPlayers([...players, { id: h.player_id, name: h.name }]); setQ(""); setHits([]); }}>
                      {h.name} <span className="text-xs text-muted-foreground">{h.club}</span></button></li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="cmp-tab">Grupo estatístico</Label>
            <Select id="cmp-tab" className="w-48" value={tab} onChange={(e) => applyTab(e.target.value)}>
              <option value="">Personalizado</option>
              {catalog && Object.entries(catalog.tabs).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </Select>
          </div>
          <div className="flex flex-wrap gap-1">
            {metrics.map((m) => (
              <span key={m} className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground">
                {label(m)} <button type="button" aria-label={`Remover ${label(m)}`} onClick={() => setMetrics(metrics.filter((x) => x !== m))}><X className="size-3" /></button>
              </span>
            ))}
          </div>
          <div className="flex items-center gap-1">
            <MetricSelect value="" className="w-56" placeholder="+ métrica" onChange={(v) => v && !metrics.includes(v) && setMetrics([...metrics, v])} />
            <Plus className="size-4 text-muted-foreground" />
          </div>
        </div>
        <UniverseControls value={universe} onChange={setUniverse} />
      </Card>
      {error && <ErrorBox message={error} />}
      {!players.length && <p className="text-sm text-muted-foreground">Adicione até quatro jogadores para comparar.</p>}
      {data && (
        <>
          <Notes notes={data.warnings} />
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="border-b text-left text-xs text-muted-foreground">
                <tr><th className="py-2 pl-3 font-medium">&nbsp;</th>
                  {data.players.map((p, i) => <th key={p.player_id} className="px-2 font-medium" style={{ color: SERIES[i] }}><PlayerLink id={p.player_id} name={p.name} /></th>)}</tr>
              </thead>
              <tbody>
                {([["Idade", (p: CmpPlayer) => p.age ?? "—"], ["Altura", (p: CmpPlayer) => (p.height ? `${p.height} cm` : "—")],
                  ["Pé", (p: CmpPlayer) => ({ left: "Esquerdo", right: "Direito", both: "Ambos" } as Record<string, string>)[p.foot ?? ""] ?? "—"],
                  ["Posição", (p: CmpPlayer) => posPt(p.position)], ["Clube", (p: CmpPlayer) => p.club ?? "—"], ["Competição", (p: CmpPlayer) => p.competition],
                  ["Minutos", (p: CmpPlayer) => fmtStat(p.minutes, "minutes")], ["CA / PA", (p: CmpPlayer) => <><AbilityPill value={p.ca} /> <AbilityPill value={p.pa} /></>],
                  ["Valor", (p: CmpPlayer) => fmtMoney(p.market_value)], ["Salário", (p: CmpPlayer) => fmtMoney(p.wage)],
                  ["Contrato", (p: CmpPlayer) => fmtDate(p.contract_expires)]] as [string, (p: CmpPlayer) => ReactNode][]).map(([t, f]) => (
                  <tr key={t} className="border-b"><td className="py-1 pl-3 text-xs text-muted-foreground">{t}</td>{data.players.map((p) => <td key={p.player_id} className="px-2">{f(p)}</td>)}</tr>
                ))}
                {data.composites.filter((c) => data.players.some((p) => p.composites[String(c.id)]?.score != null)).map((c) => (
                  <tr key={c.id} className="border-b"><td className="py-1 pl-3 text-xs text-muted-foreground">{c.name} <span className="text-[10px]">(composite)</span></td>
                    {data.players.map((p) => { const v = p.composites[String(c.id)]; return <td key={p.player_id} className="px-2 font-semibold tabular-nums">{v?.score == null ? "—" : Math.round(v.score)}</td>; })}</tr>
                ))}
                {data.metrics.map((m) => (
                  <tr key={m.key} className="border-b last:border-0">
                    <td className="py-1.5 pl-3">{m.label}{m.direction === "lower" && <span className="ml-1 text-xs text-muted-foreground">↓</span>}</td>
                    {data.players.map((p) => {
                      const c = p.metrics[m.key];
                      return (
                        <td key={p.player_id} className="px-2">
                          <div className="flex items-center gap-2"><span className="w-14 text-right tabular-nums">{fmtStat(c?.value, m.unit)}</span><PctCell p={c?.percentile} compact /></div>
                          {c?.rank != null && <div className="text-[10px] text-muted-foreground">{c.rank}.º de {c.universe}{m.key.endsWith("@p90") ? ` · total ${fmtStat(c.total, "count")}` : ""}</div>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Percentis por métrica</CardTitle></CardHeader>
              <CardContent>
                <div style={{ height: Math.max(220, data.metrics.length * 34) }}>
                  <ResponsiveContainer>
                    <BarChart data={chartRows} layout="vertical" margin={{ left: 0, right: 16 }} barCategoryGap={6} barGap={2}>
                      <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                      <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                      <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                      <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {data.players.map((p, i) => <Bar key={p.player_id} dataKey={`p${i}`} name={p.name} fill={SERIES[i]} radius={[0, 4, 4, 0]} maxBarSize={10} isAnimationActive={false} />)}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Radar de percentis</CardTitle></CardHeader>
              <CardContent>
                {chartRows.length < 3 ? <p className="text-sm text-muted-foreground">Escolha pelo menos 3 métricas.</p> : (
                  <div className="h-80">
                    <ResponsiveContainer>
                      <RadarChart data={chartRows} outerRadius="65%" margin={{ top: 8, bottom: 8, left: 40, right: 40 }}>
                        <PolarGrid stroke="hsl(var(--border))" />
                        <PolarAngleAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                        {data.players.map((p, i) => <Radar key={p.player_id} name={p.name} dataKey={`p${i}`} stroke={SERIES[i]} strokeDasharray={DASH[i]} strokeWidth={2} fill={SERIES[i]} fillOpacity={0.08} isAnimationActive={false} />)}
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          <p className="text-xs text-muted-foreground">Universo: {data.universe}. Cada percentil é relativo ao universo do próprio jogador.</p>
        </>
      )}
    </div>
  );
}
