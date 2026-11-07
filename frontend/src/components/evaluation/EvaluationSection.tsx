import { AlertTriangle, ChevronDown, ChevronUp, FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import { getJson, type MetricResult, type PlayerEvaluation, type RankedNeighbour } from "@/api";
import { ErrorBox } from "@/components/common";
import { ConfidenceBadge, ScoreBar, ScoreValue } from "@/components/evaluation/common";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCareer } from "@/lib/career";
import { CATEGORY_ORDER, scoreTone, useEvaluation } from "@/lib/evaluation";
import { cn } from "@/lib/utils";

// Disposição do campo para as 12 posições avaliadas (ataque em cima).
const PITCH: (string | null)[][] = [
  [null, "ST", null],
  ["AML", "AMC", "AMR"],
  ["ML", "MC", "MR"],
  [null, "DM", null],
  ["DL", "DC", "DR"],
  [null, "GK", null],
];

export function EvaluationSection({ playerId, runId }: { playerId: number; runId: number | null }) {
  const { catalog, posPt, posName } = useEvaluation();
  const [focus, setFocus] = useState<string | null>(null);
  const [data, setData] = useState<PlayerEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const q = new URLSearchParams();
    if (runId) q.set("run_id", String(runId));
    if (focus) q.set("position", focus);
    getJson<PlayerEvaluation>(`/api/players/${playerId}/evaluation?${q}`, ctrl.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, [playerId, runId, focus]);

  if (error) return <ErrorBox message={`Avaliação indisponível: ${error}`} />;
  if (!data || !catalog) return <Card className="p-4 text-sm text-muted-foreground">A calcular avaliação…</Card>;

  const pos = Object.fromEntries(data.positions.map((p) => [p.key, p]));
  const f = data.focus ? pos[data.focus] : null;
  const eligibleRoles = data.roles.filter((r) => r.eligible);
  const otherRoles = data.roles.filter((r) => !r.eligible);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-wrap">
          <CardTitle>Avaliação por posição e função</CardTitle>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span title={`hash ${data.model.spec_hash}`}>
              Modelo: <Link to="/lab" className="text-primary hover:underline">{data.model.name}</Link>
            </span>
            {f && <ConfidenceBadge c={f.confidence} coverage={f.coverage} />}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Indicadores <b>calculados</b> a partir dos atributos (0–100), não são valores do jogo nem estatísticas.
            {data.data_status === "estimate" && (
              <span className="ml-1 inline-flex items-center gap-1 text-warning">
                <FlaskConical className="size-3" /> Atributos fictícios (demonstração).
              </span>
            )}
            {data.stored_state === "stale" && (
              <span className="ml-1 inline-flex items-center gap-1 text-warning">
                <AlertTriangle className="size-3" /> Os pesos mudaram desde o último cálculo: os rankings precisam de ser recalculados no Position Lab.
              </span>
            )}
          </p>

          <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)_minmax(0,1fr)]">
            {/* Campo com as 12 posições */}
            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Position Scores</div>
              <div className="grid gap-1.5 rounded-lg border border-pitch-line bg-pitch p-2.5">
                {PITCH.map((row, i) => (
                  <div key={i} className="grid grid-cols-3 gap-1.5">
                    {row.map((k, j) =>
                      k ? (
                        <button
                          key={k}
                          type="button"
                          onClick={() => setFocus(k)}
                          title={`${posName(k)}${pos[k]?.eligible ? " (competente)" : ""} — média da posição ${pos[k]?.position_mean ?? "—"}`}
                          className={cn(
                            "rounded-md border bg-card/80 py-1 text-center leading-tight transition-colors hover:border-primary",
                            pos[k]?.eligible ? "border-primary/60" : "border-dashed border-pitch-line opacity-75",
                            data.focus === k && "ring-2 ring-primary",
                          )}
                        >
                          <div className="text-[10px] font-semibold text-muted-foreground">{posPt(k)}</div>
                          <ScoreValue v={pos[k]?.score} className="text-sm" />
                        </button>
                      ) : (
                        <div key={j} />
                      ),
                    )}
                  </div>
                ))}
              </div>
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Contorno cheio = posição em que é competente. Clique numa posição para a analisar.
              </p>
            </div>

            {/* Funções */}
            <div>
              <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Role Scores</div>
              <RoleList roles={eligibleRoles} posPt={posPt} />
              {otherRoles.length > 0 && <OtherRoles roles={otherRoles} posPt={posPt} />}
              <p className="mt-2 text-[11px] text-muted-foreground">Funções por confirmar na versão do FM27 instalada.</p>
            </div>

            {/* Posição em análise */}
            {f && (
              <div className="space-y-3">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <div className="text-xs text-muted-foreground">Posição em análise</div>
                    <div className="text-lg font-semibold">{posName(f.key)} ({posPt(f.key)})</div>
                  </div>
                  <div className="text-right">
                    <ScoreValue v={f.score} className="text-3xl" />
                    <div className="text-xs text-muted-foreground">média {data.position_mean_score ?? "—"} · {data.position_players} competentes</div>
                  </div>
                </div>
                {data.ranking ? (
                  <div className="rounded-md bg-muted/50 p-2.5 text-sm">
                    <b>{data.ranking.rank}.º</b> de {data.ranking.of} jogadores competentes em {posPt(f.key)}
                    {data.ranking.percentile !== null && <span className="text-muted-foreground"> · percentil {Math.round(data.ranking.percentile)}</span>}
                    <Neighbours r={data.ranking} />
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {f.eligible ? "Sem ranking (avaliação por recalcular)." : "Não é competente nesta posição: fica fora do ranking."}
                  </p>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Pontos fortes e fracos {f && <span className="font-normal text-muted-foreground">— como {posPt(f.key)}</span>}</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <StrengthList title="Pontos fortes" items={data.strengths} positive />
            <StrengthList title="Pontos fracos" items={data.weaknesses} />
          </CardContent>
        </Card>
        <AttributeRadar data={data} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Comparação com a média da posição {f && `(${posPt(f.key)})`}</CardTitle>
          <span className="text-xs text-muted-foreground">traço = média dos competentes na posição</span>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-x-8 sm:grid-cols-2">
            {data.comparison.map((c) => (
              <li key={c.metric} className="grid grid-cols-[minmax(0,1fr)_90px_32px_44px] items-center gap-2 border-b border-dashed py-1 text-sm">
                <span className="truncate" title={`${Math.round(c.weight_share * 100)}% do peso da posição`}>
                  {c.name} <span className="text-[10px] text-muted-foreground">{Math.round(c.weight_share * 100)}%</span>
                </span>
                <ScoreBar v={c.score} mean={c.position_mean} />
                <ScoreValue v={c.score} className="text-right" />
                <span className={cn("text-right text-xs tabular-nums", c.diff === null ? "text-muted-foreground" : c.diff >= 0 ? "text-attr-good" : "text-attr-low")}>
                  {c.diff === null ? "—" : c.diff > 0 ? `+${c.diff.toFixed(0)}` : c.diff.toFixed(0)}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <MetricsByCategory metrics={data.metrics} />
    </div>
  );
}

function RoleList({ roles, posPt }: { roles: PlayerEvaluation["roles"]; posPt: (k: string) => string }) {
  if (roles.length === 0) return <p className="text-sm text-muted-foreground">Nenhuma função nas posições em que é competente.</p>;
  return (
    <ul className="space-y-1">
      {roles.map((r) => (
        <li key={r.key} className="grid grid-cols-[minmax(0,1fr)_80px_28px] items-center gap-2 text-sm">
          <span className="truncate" title={`${r.positions.map(posPt).join(", ")} · ${Math.round(r.coverage * 100)}% dos dados`}>
            {r.name} <span className="text-[10px] text-muted-foreground">{r.positions.map(posPt).join("/")}</span>
          </span>
          <ScoreBar v={r.score} />
          <ScoreValue v={r.score} className="text-right" />
        </li>
      ))}
    </ul>
  );
}

function OtherRoles({ roles, posPt }: { roles: PlayerEvaluation["roles"]; posPt: (k: string) => string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button type="button" className="inline-flex items-center gap-1 text-xs text-primary hover:underline" onClick={() => setOpen((v) => !v)}>
        {open ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />} Outras funções ({roles.length})
      </button>
      {open && <div className="mt-1.5 opacity-80"><RoleList roles={roles} posPt={posPt} /></div>}
    </div>
  );
}

function Neighbours({ r }: { r: NonNullable<PlayerEvaluation["ranking"]> }) {
  const row = (p: RankedNeighbour) => (
    <li key={p.player_id} className="flex items-center justify-between gap-2">
      <Link to={`/jogador/${p.player_id}`} className="truncate hover:underline">{p.name}</Link>
      <span className="shrink-0 text-xs text-muted-foreground">{p.age ?? "—"} a · CA {p.ca ?? "—"}</span>
      <ScoreValue v={p.score} className="w-7 shrink-0 text-right" />
    </li>
  );
  return (
    <div className="mt-2 grid gap-3 sm:grid-cols-2">
      <div>
        <div className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Top 5</div>
        <ol className="space-y-0.5 text-xs">{r.top.map(row)}</ol>
      </div>
      <div>
        <div className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Logo acima / abaixo</div>
        <ol className="space-y-0.5 text-xs">
          {r.above.map(row)}
          <li className="text-center text-[11px] text-muted-foreground">— este jogador —</li>
          {r.below.map(row)}
        </ol>
      </div>
    </div>
  );
}

function StrengthList({ title, items, positive }: { title: string; items: PlayerEvaluation["strengths"]; positive?: boolean }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{positive ? "Nada claramente acima da média." : "Nada claramente abaixo da média."}</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((x) => (
            <li key={x.metric} className="text-sm">
              <div className="flex items-center justify-between gap-2">
                <span>{x.name}</span>
                <span className={cn("text-xs font-semibold tabular-nums", positive ? "text-attr-good" : "text-attr-low")}>
                  {positive ? "▲" : "▼"} {x.diff !== null && (x.diff > 0 ? `+${x.diff.toFixed(0)}` : x.diff.toFixed(0))}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                {Math.round(x.score ?? 0)} contra média {Math.round(x.position_mean ?? 0)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AttributeRadar({ data }: { data: PlayerEvaluation }) {
  const rows = data.attributes_vs_position
    .filter((a) => a.value !== null)
    .map((a) => ({ label: a.label, player: a.value, mean: a.position_mean !== null ? Math.round(a.position_mean * 10) / 10 : null }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Radar de atributos</CardTitle>
        <span className="text-xs text-muted-foreground">os 8 atributos com mais peso na posição</span>
      </CardHeader>
      <CardContent>
        {rows.length < 3 ? (
          <p className="text-sm text-muted-foreground">Sem dados suficientes para o radar.</p>
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer>
              <RadarChart data={rows} outerRadius="66%" margin={{ top: 8, right: 36, bottom: 8, left: 36 }}>
                <PolarGrid stroke="hsl(var(--border))" />
                <PolarAngleAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <PolarRadiusAxis domain={[0, 20]} tick={false} axisLine={false} />
                <Radar name="Média da posição" dataKey="mean" stroke="hsl(var(--chart-ref))" strokeDasharray="4 3" fill="none" isAnimationActive={false} />
                <Radar name="Jogador" dataKey="player" stroke="hsl(var(--chart-1))" strokeWidth={2} fill="hsl(var(--chart-1))" fillOpacity={0.22}
                  dot={{ r: 3, fill: "hsl(var(--chart-1))" }} isAnimationActive={false} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MetricsByCategory({ metrics }: { metrics: MetricResult[] }) {
  const { catalog } = useEvaluation();
  const { attrLabel } = useCareer();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Métricas calculadas</CardTitle>
        <span className="text-xs text-muted-foreground">clique numa métrica para ver os atributos usados</span>
      </CardHeader>
      <CardContent className="grid gap-x-8 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
        {CATEGORY_ORDER.map((cat) => {
          const list = metrics.filter((m) => m.category === cat);
          if (!list.length) return null;
          return (
            <div key={cat}>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{catalog?.categories[cat] ?? cat}</div>
              <ul>
                {list.map((m) => (
                  <li key={m.key} className="border-b border-dashed last:border-0">
                    <button
                      type="button"
                      onClick={() => setOpen(open === m.key ? null : m.key)}
                      className="grid w-full grid-cols-[minmax(0,1fr)_70px_28px] items-center gap-2 py-1 text-left text-sm hover:bg-muted/50"
                    >
                      <span className="truncate">
                        {m.name}
                        {m.coverage < 1 && (
                          <span className="ml-1 text-[10px] text-warning" title={`Faltam: ${m.missing.map(attrLabel).join(", ")}`}>
                            {Math.round(m.coverage * 100)}%
                          </span>
                        )}
                      </span>
                      <ScoreBar v={m.score} />
                      <ScoreValue v={m.score} className="text-right" />
                    </button>
                    {open === m.key && (
                      <div className="mb-2 rounded-md bg-muted/50 p-2 text-xs">
                        <ul className="space-y-0.5">
                          {m.attributes.map((a) => (
                            <li key={a.attribute} className="flex justify-between gap-2">
                              <span>
                                {attrLabel(a.attribute)}
                                {a.invert && <span className="text-muted-foreground"> (invertido)</span>}
                              </span>
                              <span className="tabular-nums text-muted-foreground">
                                {a.value} → {Math.round(a.normalized)} · peso {a.weight}
                              </span>
                            </li>
                          ))}
                          {m.missing.map((k) => (
                            <li key={k} className="flex justify-between text-warning">
                              <span>{attrLabel(k)}</span>
                              <span>em falta (não conta)</span>
                            </li>
                          ))}
                        </ul>
                        <div className="mt-1 flex items-center gap-2">
                          <Badge variant="secondary" className="font-normal">cobertura {Math.round(m.coverage * 100)}%</Badge>
                          <span className={scoreTone(m.score)}>{m.score === null ? "não calculada (dados insuficientes)" : ""}</span>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
