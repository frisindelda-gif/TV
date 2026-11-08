import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getJson, type PlayerPage } from "@/api";
import { ErrorBox } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import type { PartitionStats, StatPlayer, UniverseIn } from "@/stats/api";
import { DEFAULT_UNIVERSE, GROUP_SHORT, GroupSelect, MetricSelect, PctCell, PlayerLink, UniverseControls, posPt } from "@/stats/components";
import { fmtStat, useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

type PlayerPct = { universe: string; percentile: number | null; rank: number | null; of: number; mean: number | null };
type Analysis = {
  metric: string; label: string; unit: string; direction: string; universe: string;
  histogram: { from: number; to: number; players: number }[];
  partitions: (PartitionStats & { key: string })[];
  top: (StatPlayer & { value: number | null; percentile: number | null; rank: number | null })[];
  player: { name: string; value: number | null; position: PlayerPct; competition: PlayerPct; population: PlayerPct | null } | null;
};

const AXIS = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };

export default function StatsPercentiles() {
  const { career } = useCareer();
  const { unit } = useStats();
  const [metric, setMetric] = useState("pass_pct");
  const [group, setGroup] = useState("CM");
  const [universe, setUniverse] = useState<UniverseIn>(DEFAULT_UNIVERSE);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlayerPage["items"]>([]);
  const [playerId, setPlayerId] = useState<number | null>(null);

  const qs = new URLSearchParams({ metric, universe_competition: universe.competition, position_level: universe.position_level,
    min_minutes: String(universe.min_minutes), min_sample: String(universe.min_sample) });
  if (career) qs.set("career_id", String(career.id));
  if (group) qs.set("group", group);
  if (universe.shortlist_id) qs.set("shortlist_id", String(universe.shortlist_id));
  if (playerId) qs.set("player_id", String(playerId));
  const { data, error, loading } = useStatsQuery<Analysis>(career && metric ? `/api/stats/percentile-analysis?${qs}` : null);

  const search = (v: string) => {
    setQ(v);
    if (!career || v.length < 2) return setHits([]);
    getJson<PlayerPage>(`/api/players?career_id=${career.id}&q=${encodeURIComponent(v)}&limit=8`).then((p) => setHits(p.items)).catch(() => {});
  };
  const u = unit(metric);

  return (
    <div className="space-y-3">
      <Card className="space-y-3 p-3">
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <div className="col-span-2 space-y-1"><Label>Métrica</Label><MetricSelect value={metric} group={group} onlyPercentile onChange={setMetric} /></div>
          <div className="space-y-1"><Label htmlFor="pa-group">Posição</Label><GroupSelect id="pa-group" value={group} onChange={setGroup} /></div>
          <div className="relative space-y-1">
            <Label htmlFor="pa-player">Jogador (opcional)</Label>
            <Input id="pa-player" value={q} placeholder="Procurar…" onChange={(e) => search(e.target.value)} />
            {hits.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full rounded-md border bg-card shadow">
                {hits.map((h) => (
                  <li key={h.player_id}><button type="button" className="w-full px-2 py-1 text-left text-sm hover:bg-muted"
                    onClick={() => { setPlayerId(h.player_id); setQ(h.name); setHits([]); }}>{h.name}</button></li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <UniverseControls value={universe} onChange={setUniverse} />
      </Card>
      {error && <ErrorBox message={error} />}
      {data && (
        <>
          {data.player && (
            <Card>
              <CardHeader><CardTitle>{data.player.name}: {data.label} = {fmtStat(data.player.value, u)}</CardTitle></CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-3">
                {([["Percentil na posição", data.player.position], ["Percentil na competição", data.player.competition],
                  ["Percentil na população selecionada", data.player.population]] as [string, PlayerPct | null][]).map(([t, p]) => (
                  <div key={t} className="rounded-md border p-2.5">
                    <div className="text-xs text-muted-foreground">{t}</div>
                    {p ? (
                      <>
                        <div className="mt-1 text-2xl font-semibold tabular-nums">{p.percentile == null ? "—" : Math.round(p.percentile)}</div>
                        <div className="text-xs text-muted-foreground">{p.rank ? `${p.rank}.º de ${p.of}` : "amostra insuficiente"} · média {fmtStat(p.mean, u)}</div>
                        <div className="mt-1 text-[11px] text-muted-foreground">{p.universe}</div>
                      </>
                    ) : <div className="mt-1 text-sm text-muted-foreground">Escolha uma shortlist em "População".</div>}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className={loading ? "opacity-60" : ""}>
              <CardHeader><CardTitle>Distribuição — {data.label}</CardTitle>
                <span className="text-xs text-muted-foreground">{data.direction === "lower" ? "menos é melhor" : "mais é melhor"}</span></CardHeader>
              <CardContent>
                {data.histogram.length === 0 ? <p className="text-sm text-muted-foreground">Sem valores neste universo (métrica indisponível neste save ou sem jogadores elegíveis).</p> : (
                  <div className="h-60">
                    <ResponsiveContainer>
                      <BarChart data={data.histogram.map((h) => ({ ...h, label: fmtStat(h.from, u) }))} margin={{ top: 4, right: 4, bottom: 0, left: -20 }} barCategoryGap={2}>
                        <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={AXIS} />
                        <YAxis allowDecimals={false} tick={AXIS} />
                        <Tooltip cursor={{ fill: "hsl(var(--muted))" }} contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
                          labelFormatter={(_l, p) => { const x = p?.[0]?.payload as { from: number; to: number } | undefined; return x ? `${fmtStat(x.from, u)} – ${fmtStat(x.to, u)}` : ""; }}
                          formatter={(v) => [String(v), "Jogadores"]} />
                        <Bar dataKey="players" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Universos de comparação</CardTitle></CardHeader>
              <CardContent className="overflow-x-auto">
                <table className="w-full text-xs tabular-nums">
                  <thead className="text-left text-muted-foreground"><tr><th className="py-1 font-medium">Competição</th><th className="font-medium">Pos.</th><th className="text-right font-medium">N</th><th className="text-right font-medium">Média</th><th className="text-right font-medium">Mediana</th><th className="text-right font-medium">Melhor</th><th className="text-right font-medium">Pior</th><th className="text-right font-medium">Cobert.</th></tr></thead>
                  <tbody>
                    {data.partitions.map((p) => (
                      <tr key={p.key} className="border-t">
                        <td className="py-1">{p.competition}</td><td>{GROUP_SHORT[p.position] ?? posPt(p.position)}</td>
                        <td className="text-right">{p.with_value}{!p.sufficient && <span className="ml-0.5 text-warning" title="amostra insuficiente">!</span>}</td>
                        <td className="text-right">{fmtStat(p.mean, u)}</td><td className="text-right">{fmtStat(p.median, u)}</td>
                        <td className="text-right">{fmtStat(p.best, u)}</td><td className="text-right">{fmtStat(p.worst, u)}</td>
                        <td className="text-right">{p.coverage == null ? "—" : `${Math.round(p.coverage * 100)}%`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-[11px] text-muted-foreground">Universo: {data.universe}. Percentis de competições diferentes não são diretamente comparáveis.</p>
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader><CardTitle>Melhores percentis</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm">
                <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Jogador</th><th className="font-medium">Pos.</th><th className="font-medium">Competição</th><th className="text-right font-medium">Valor</th><th className="font-medium">Percentil</th><th className="text-right font-medium">Ranking</th></tr></thead>
                <tbody>
                  {data.top.map((p) => (
                    <tr key={p.player_id} className="border-t">
                      <td className="py-1"><PlayerLink id={p.player_id} name={p.name} /> <span className="text-xs text-muted-foreground">{p.age}</span></td>
                      <td className="text-xs">{posPt(p.position)}</td><td className="text-xs text-muted-foreground">{p.competition}</td>
                      <td className="text-right tabular-nums">{fmtStat(p.value, u)}</td><td><PctCell p={p.percentile} /></td>
                      <td className="text-right tabular-nums">{p.rank ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
