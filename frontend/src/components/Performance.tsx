import { useState } from "react";
import { Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import type { PlayerMetrics } from "@/api";
import { StatusBadge } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCareer } from "@/lib/career";
import { METRIC_GROUP_LABEL, fmtInt, fmtMetric } from "@/lib/format";
import { cn } from "@/lib/utils";

// Rótulos curtos para o radar (os completos aparecem na lista e no tooltip).
const RADAR_SHORT: Record<string, string> = {
  progressive_passes_90: "Passes progr.",
  key_passes_90: "Passes decis.",
  pass_pct: "Passe %",
  possession_won_90: "Posse ganha",
  tackles_90: "Desarmes",
  interceptions_90: "Interceções",
  headers_won_90: "Cabeceam.",
  aerial_pct: "Aéreos %",
  clearances_90: "Alívios",
  distance_90: "Distância",
  average_rating: "Nota",
  shots_on_target_pct: "À baliza %",
  conversion_pct: "Conversão %",
  cross_pct: "Cruzam. %",
  pressures_90: "Pressões",
  ccc_90: "Ocasiões",
  save_pct: "Defesas %",
  xgp_90: "xGP",
  goals_allowed_90: "Sofridos",
  clean_sheet_pct: "Sem sofrer %",
  npxg_90: "npxG",
  goals_90: "Golos",
  xg_90: "xG",
  xa_90: "xA",
  shots_90: "Remates",
  dribbles_90: "Dribles",
  sprints_90: "Sprints",
};

const GROUP_ORDER = ["attack", "creation", "defence", "goalkeeping", "physical", "general"] as const;

type Props = { metrics: PlayerMetrics | null; connector: string };

export function PerformanceCard({ metrics, connector }: Props) {
  const { metricDef } = useCareer();
  const [showAll, setShowAll] = useState(false);

  if (!metrics) {
    return (
      <Card>
        <CardHeader><CardTitle>Desempenho</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {connector === "live_memory"
              ? "A leitura da memória não inclui estatísticas, por isso não há métricas. Importe o save (.fm) para as ver."
              : "Sem minutos jogados nesta época."}
          </p>
        </CardContent>
      </Card>
    );
  }

  const m = metrics;
  const hasPct = Object.keys(m.percentiles).length > 0;
  const radarData = m.radar
    .filter((k) => m.percentiles[k] !== undefined)
    .map((k) => ({
      key: k,
      label: RADAR_SHORT[k] ?? (metricDef(k)?.label ?? k).replace(" /90", ""),
      pct: m.percentiles[k],
      median: 50,
      value: fmtMetric(m.values[k], metricDef(k)?.unit),
    }));

  const grouped = GROUP_ORDER.map((g) => ({
    group: g,
    items: Object.keys(m.values)
      .map((k) => ({ key: k, def: metricDef(k) }))
      .filter((x) => x.def?.group === g && x.def.unit !== "minutes" && x.key !== "appearances")
      .filter((x) => showAll || m.values[x.key] !== null),
  })).filter((g) => g.items.length > 0);

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>Desempenho na época</CardTitle>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>{fmtInt(Math.round(m.minutes))} min · {m.appearances} jogos</span>
          <StatusBadge status={m.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Calculado a partir das estatísticas do jogo (por 90 minutos e percentagens).{" "}
          {hasPct ? (
            <>
              Percentil = posição entre os <b className="text-foreground">{m.peers} {m.position_group_label?.toLowerCase()}</b>{" "}
              com pelo menos {m.min_minutes} minutos nesta importação (100 = o melhor).
            </>
          ) : m.enough_minutes ? (
            <>Não há jogadores suficientes da mesma posição para calcular percentis.</>
          ) : (
            <>Menos de {m.min_minutes} minutos jogados: amostra pequena, sem percentis.</>
          )}
        </p>

        <div className={cn("grid gap-6", radarData.length >= 3 && "lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]")}>
          {radarData.length >= 3 && (
            <figure>
              <figcaption className="mb-1 text-xs font-medium text-muted-foreground">
                Perfil de {m.position_group_label?.toLowerCase()} (percentis)
              </figcaption>
              <div className="h-[300px]">
                <ResponsiveContainer>
                  <RadarChart data={radarData} outerRadius="62%" margin={{ top: 8, right: 40, bottom: 8, left: 40 }}>
                    <PolarGrid stroke="hsl(var(--border))" />
                    <PolarAngleAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} tickCount={5} />
                    <Radar
                      name="Mediana da posição"
                      dataKey="median"
                      stroke="hsl(var(--chart-ref))"
                      strokeDasharray="4 3"
                      strokeWidth={1.5}
                      fill="none"
                      isAnimationActive={false}
                    />
                    <Radar
                      name="Jogador"
                      dataKey="pct"
                      stroke="hsl(var(--chart-1))"
                      strokeWidth={2}
                      fill="hsl(var(--chart-1))"
                      fillOpacity={0.22}
                      dot={{ r: 3, fill: "hsl(var(--chart-1))" }}
                      isAnimationActive={false}
                    />
                    <Tooltip
                      labelFormatter={(_l, pl) => {
                        const k = (pl?.[0]?.payload as { key?: string })?.key;
                        return k ? metricDef(k)?.label ?? k : "";
                      }}
                      formatter={(v, name, item) =>
                        name === "Jogador" ? [`percentil ${v} · ${(item.payload as { value: string }).value}`, name] : [String(v), name]
                      }
                      contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </figure>
          )}

          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {grouped.map((g) => (
              <div key={g.group}>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {METRIC_GROUP_LABEL[g.group]}
                </div>
                <ul>
                  {g.items.map(({ key, def }) => (
                    <MetricRow
                      key={key}
                      label={def?.label ?? key}
                      value={fmtMetric(m.values[key], def?.unit)}
                      pct={m.percentiles[key]}
                      lowerIsBetter={def?.higher_is_better === false}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <button type="button" className="text-xs text-primary hover:underline" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Esconder métricas sem dados" : "Mostrar também métricas sem dados"}
        </button>
      </CardContent>
    </Card>
  );
}

function MetricRow({ label, value, pct, lowerIsBetter }: { label: string; value: string; pct?: number; lowerIsBetter: boolean }) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto_64px_28px] items-center gap-2 border-b border-dashed py-1 text-sm last:border-0">
      <span className="truncate" title={lowerIsBetter ? `${label} (menos é melhor)` : label}>
        {label}
        {lowerIsBetter && <span className="ml-1 text-[10px] text-muted-foreground">↓</span>}
      </span>
      <span className="text-right font-medium tabular-nums">{value}</span>
      {pct !== undefined ? (
        <>
          <span className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
            <span className="block h-full rounded-full bg-chart-1" style={{ width: `${Math.max(2, pct)}%` }} />
          </span>
          <span className="text-right text-xs tabular-nums text-muted-foreground" title="Percentil na posição">
            {Math.round(pct)}
          </span>
        </>
      ) : (
        <span className="col-span-2" />
      )}
    </li>
  );
}
