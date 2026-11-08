import { useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBox } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { MetricCell, ProfileRow, StatProfile } from "@/stats/api";
import { MetricSelect, PctCell, StatusBadge } from "@/stats/components";
import { fmtStat, useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

const TABS: [string, string][] = [
  ["overview", "Overview"], ["defensive", "Defensive"], ["passing", "Passing"], ["progression", "Progression"],
  ["attacking", "Attacking"], ["physical_duels", "Physical/Duels"], ["pressing", "Pressing"], ["percentiles", "Percentiles"],
  ["history", "Historical Development"],
];

export function StatsProfileSection({ playerId, runId }: { playerId: number; runId: number | null }) {
  const [tab, setTab] = useState("overview");
  const [showAll, setShowAll] = useState(false);
  const url = `/api/stats/players/${playerId}/profile${runId ? `?run_id=${runId}` : ""}`;
  const { data, error } = useStatsQuery<StatProfile>(url);

  if (error) return <ErrorBox message={`Estatísticas: ${error}`} />;
  if (!data) return <Card className="p-4 text-sm text-muted-foreground">A carregar estatísticas…</Card>;
  if (!data.player)
    return (
      <Card>
        <CardHeader><CardTitle>Statistical Scouting</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">{data.reason}</CardContent>
      </Card>
    );

  const rows: ProfileRow[] = tab === "overview" ? data.overview : tab === "percentiles" ? data.percentiles : data.tabs[tab]?.rows ?? [];
  const visible = showAll || tab === "overview" || tab === "percentiles" ? rows : rows.filter((r) => !["UNAVAILABLE", "PARTIAL", "INVALID"].includes(r.status));
  const hidden = rows.length - visible.length;

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>Statistical Scouting</CardTitle>
        <span className="text-xs text-muted-foreground">
          {data.group_label} · {data.scope_label} · {Math.round(data.player.minutes ?? 0)} min · universo: {data.universe}
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-1 overflow-x-auto pb-1" role="tablist">
          {TABS.map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} type="button" onClick={() => setTab(k)}
              className={cn("shrink-0 rounded-full border px-3 py-1 text-xs font-medium", tab === k ? "border-primary bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted")}>
              {l}
            </button>
          ))}
        </div>

        {tab === "overview" && data.composites.some((c) => c.applies) && (
          <div className="grid gap-2 sm:grid-cols-2">
            {data.composites.filter((c) => c.applies).map((c) => (
              <div key={c.id} className="rounded-md border p-2.5">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm font-medium">{c.name}</span>
                  <span className="text-xl font-semibold tabular-nums">{c.score == null ? "—" : Math.round(c.score)}</span>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  Composite Score (calculado) · {c.coverage == null ? "fora do universo" : `${Math.round(c.coverage * 100)}% dos componentes com dados`}
                </div>
                <ul className="mt-1 space-y-0.5 text-xs">
                  {c.components.map((x) => (
                    <li key={x.metric} className="flex items-center justify-between gap-2">
                      <span className={x.percentile == null ? "text-muted-foreground line-through" : ""} title={x.percentile == null ? "sem dados: fica de fora" : undefined}>{x.label}</span>
                      <PctCell p={x.percentile} compact />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {tab === "history" ? (
          <History playerId={playerId} />
        ) : (
          <>
            <MetricTable rows={visible} />
            {hidden > 0 && (
              <button type="button" className="text-xs text-primary hover:underline" onClick={() => setShowAll(true)}>
                Mostrar também {hidden} métricas indisponíveis neste save
              </button>
            )}
            {tab === "overview" && <p className="text-xs text-muted-foreground">Métricas principais da posição com dados neste save. <Link className="text-primary underline" to="/stats/availability">Disponibilidade</Link></p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function MetricTable({ rows }: { rows: ProfileRow[] }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">Sem métricas com dados neste separador.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead className="text-left text-xs text-muted-foreground">
          <tr>
            <th className="py-1 font-medium">Métrica</th><th className="text-right font-medium">Valor</th><th className="text-right font-medium">Total</th>
            <th className="font-medium">Percentil</th><th className="text-right font-medium">Ranking</th><th className="text-right font-medium">Média</th>
            <th className="font-medium">Estado</th><th className="font-medium">Fonte</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t">
              <td className="py-1 pr-2">
                {r.label}
                {r.direction === "lower" && <span className="ml-1 text-xs text-muted-foreground" title="menos é melhor">↓</span>}
                {r.composed && <span className="ml-1 text-[10px] text-warning">composto</span>}
              </td>
              <td className="pr-2 text-right font-medium tabular-nums">{fmtStat(r.value, r.unit)}</td>
              <td className="pr-2 text-right tabular-nums text-muted-foreground">{r.view === "p90" ? fmtStat(r.total, "count") : ""}</td>
              <td className="pr-2"><PctCell p={r.percentile} /></td>
              <td className="pr-2 text-right text-xs tabular-nums">{r.rank != null ? `${r.rank}.º / ${r.universe}` : r.universe ? `amostra ${r.universe}` : "—"}</td>
              <td className="pr-2 text-right tabular-nums text-muted-foreground">{fmtStat(r.universe_mean, r.unit)}</td>
              <td className="pr-2"><StatusBadge status={r.status} title={r.reason} /></td>
              <td className="max-w-[220px] truncate text-[11px] text-muted-foreground" title={r.source}>{r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type HistoryPoint = { run_id: number; game_date: string | null; season: string | null; minutes: number | null; values: Record<string, MetricCell> };

function History({ playerId }: { playerId: number }) {
  const { label, unit } = useStats();
  const [metric, setMetric] = useState("goals@p90");
  const { data } = useStatsQuery<HistoryPoint[]>(`/api/stats/players/${playerId}/history?metrics=${encodeURIComponent(metric)}`);
  const u = unit(metric);
  const rows = (data ?? []).map((h) => ({ season: h.season ?? h.game_date ?? `#${h.run_id}`, value: h.values[metric]?.value ?? null,
    pct: h.values[metric]?.percentile ?? null, minutes: h.minutes }));
  return (
    <div className="space-y-2">
      <div className="w-72"><MetricSelect value={metric} onChange={(v) => v && setMetric(v)} /></div>
      {rows.length < 2 ? (
        <p className="text-sm text-muted-foreground">A evolução aparece com duas ou mais importações com estatísticas deste jogador.</p>
      ) : (
        <div className="h-56">
          <ResponsiveContainer>
            <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="season" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
              <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickFormatter={(v: number) => fmtStat(v, u)} />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
                formatter={(v) => [fmtStat(Number(v), u), label(metric)]} />
              <Line dataKey="value" name={label(metric)} stroke="hsl(var(--chart-1))" strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <table className="w-full max-w-xl text-sm tabular-nums">
        <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Época</th><th className="text-right font-medium">Minutos</th><th className="text-right font-medium">{label(metric)}</th><th className="font-medium">Percentil</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.season} className="border-t"><td className="py-1">{r.season}</td><td className="text-right">{fmtStat(r.minutes, "minutes")}</td>
            <td className="text-right">{fmtStat(r.value, u)}</td><td className="pl-2"><PctCell p={r.pct} /></td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
