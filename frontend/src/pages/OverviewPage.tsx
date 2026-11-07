import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getJson, type Overview, type OverviewPlayer } from "@/api";
import { AbilityPill, EmptyState, ErrorBox, SyntheticBadge } from "@/components/common";
import { POSITION_LABEL } from "@/components/PositionPitch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCareer } from "@/lib/career";
import { fmtDate, fmtInt, fmtMetric } from "@/lib/format";

const AXIS = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };
const TOOLTIP = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 };

export default function OverviewPage() {
  const { careers, career, metricDef } = useCareer();
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!career) return;
    setData(null);
    getJson<Overview>(`/api/overview?career_id=${career.id}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, [career]);

  if (careers === null) return <div className="text-sm text-muted-foreground">A carregar…</div>;
  if (!career)
    return (
      <EmptyState title="Ainda não há dados importados">
        Vá a <Link className="text-primary underline" to="/dados">Dados</Link> para importar um save, ler o jogo ou criar uma
        carreira de demonstração.
      </EmptyState>
    );
  if (error) return <ErrorBox message={error} />;
  if (!data) return <div className="text-sm text-muted-foreground">A carregar…</div>;

  const k = data.kpis;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-lg font-semibold">Painel</h1>
        <span className="text-sm text-muted-foreground">
          {career.label} · {fmtDate(data.game_date)}
          {data.season_label && ` · época ${data.season_label}`}
        </span>
        {data.synthetic && <SyntheticBadge />}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
        <Kpi label="Jogadores" value={fmtInt(k.players)} to="/jogadores" />
        <Kpi label="CA médio" value={k.avg_ca.toFixed(1).replace(".", ",")} />
        <Kpi label="Elite (CA 150+)" value={fmtInt(k.elite)} to="/jogadores?min_ca=150" />
        <Kpi label="Wonderkids" value={fmtInt(k.wonderkids)} to="/jogadores?max_age=19&min_pa=150" hint="≤19 anos, PA 150+" />
        <Kpi
          label="Novos regens"
          value={data.has_growth || k.new_players ? fmtInt(k.new_regens) : "—"}
          to="/jogadores?new_only=true&max_age=17&sort=pa&order=desc"
          hint="≤17 anos, novos nesta importação"
        />
        <Kpi label="Subiram 5+ CA" value={data.has_growth ? fmtInt(k.risers) : "—"} to="/jogadores?min_ca_delta=5&sort=ca_delta&order=desc" />
        <Kpi label="Desceram 5+ CA" value={data.has_growth ? fmtInt(k.fallers) : "—"} to="/jogadores?sort=ca_delta&order=asc" />
        <Kpi label="Com estatísticas" value={fmtInt(k.with_stats)} hint={data.has_metrics ? undefined : "importe o save"} />
      </div>
      {!data.has_growth && (
        <p className="text-xs text-muted-foreground">
          Crescimento e regens novos aparecem a partir da segunda importação desta carreira.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Histogram title="Distribuição de CA" data={data.ca_histogram} />
        <Histogram title="Distribuição de PA" data={data.pa_histogram} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.has_growth && (
          <TopList
            title="Maiores subidas de CA"
            more="/jogadores?sort=ca_delta&order=desc"
            players={data.top_risers}
            right={(p) => <span className="font-semibold tabular-nums text-attr-good">▲ +{p.ca_delta}</span>}
          />
        )}
        <TopList
          title="Melhores regens novos"
          more="/jogadores?new_only=true&max_age=18&sort=pa&order=desc"
          players={data.top_new_regens}
          empty={data.has_growth ? "Nenhum regen novo nesta importação." : "Aparece a partir da segunda importação."}
          right={(p) => <AbilityPill value={p.pa} />}
        />
        <TopList
          title="Maiores potenciais (≤21)"
          more="/jogadores?max_age=21&sort=pa&order=desc"
          players={data.top_prospects}
          right={(p) => <AbilityPill value={p.pa} />}
        />
        {data.has_metrics && (
          <>
            <TopList
              title="Melhor nota média"
              more="/jogadores?min_minutes=450&sort=m:average_rating&order=desc"
              players={data.top_rated}
              right={(p) => <span className="font-semibold tabular-nums">{fmtMetric(p.metric, "rating")}</span>}
            />
            <TopList
              title={`Mais ${metricDef("goals_90")?.label.toLowerCase() ?? "golos /90"}`}
              more="/jogadores?min_minutes=450&sort=m:goals_90&order=desc"
              players={data.top_scorers}
              right={(p) => <span className="font-semibold tabular-nums">{fmtMetric(p.metric, "per90")}</span>}
            />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Por posição</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr>
                  <th className="py-1 font-medium">Grupo</th>
                  <th className="text-right font-medium">Jogadores</th>
                  <th className="text-right font-medium">CA médio</th>
                  <th className="text-right font-medium">Melhor CA</th>
                </tr>
              </thead>
              <tbody>
                {[...data.position_groups].sort((a, b) => b.players - a.players).map((g) => (
                  <tr key={g.group ?? "none"} className="border-t tabular-nums">
                    <td className="py-1.5">
                      {g.group ? (
                        <Link className="hover:underline" to={`/jogadores?position_group=${g.group}`}>{g.label}</Link>
                      ) : (
                        g.label
                      )}
                    </td>
                    <td className="text-right">{fmtInt(g.players)}</td>
                    <td className="text-right">{g.avg_ca.toFixed(1).replace(".", ",")}</td>
                    <td className="text-right">{g.max_ca ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Clubes com CA médio mais alto</CardTitle></CardHeader>
          <CardContent>
            <div style={{ height: Math.max(160, data.clubs.length * 30) }}>
              <ResponsiveContainer>
                <BarChart data={data.clubs} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barCategoryGap={6}>
                  <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, (max: number) => Math.ceil(max / 20) * 20]} allowDecimals={false} tick={AXIS} />
                  <YAxis type="category" dataKey="name" width={150} tick={AXIS} />
                  <Tooltip
                    cursor={{ fill: "hsl(var(--muted))" }}
                    contentStyle={TOOLTIP}
                    formatter={(v, _n, item) => [
                      `${Number(v).toFixed(1).replace(".", ",")} (${(item.payload as { players: number }).players} jogadores)`,
                      "CA médio",
                    ]}
                  />
                  <Bar dataKey="avg_ca" name="CA médio" fill="hsl(var(--chart-1))" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value, hint, to }: { label: string; value: string; hint?: string; to?: string }) {
  const body = (
    <Card className="h-full p-3 transition-colors hover:border-primary/50">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-muted-foreground">{hint}</div>}
    </Card>
  );
  return to ? <Link to={to} className="block">{body}</Link> : body;
}

function Histogram({ title, data }: { title: string; data: Overview["ca_histogram"] }) {
  const rows = data.map((b) => ({ ...b, label: `${b.from}–${b.to}` }));
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <div className="h-52">
          <ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -20 }} barCategoryGap={2}>
              <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
              <XAxis dataKey="from" tick={AXIS} />
              <YAxis allowDecimals={false} tick={AXIS} />
              <Tooltip
                cursor={{ fill: "hsl(var(--muted))" }}
                contentStyle={TOOLTIP}
                labelFormatter={(_l, p) => (p?.[0]?.payload as { label?: string })?.label ?? ""}
                formatter={(v) => [fmtInt(Number(v)), "Jogadores"]}
              />
              <Bar dataKey="players" name="Jogadores" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function TopList(props: {
  title: string;
  players: OverviewPlayer[];
  right: (p: OverviewPlayer) => ReactNode;
  more?: string;
  empty?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{props.title}</CardTitle>
        {props.more && props.players.length > 0 && (
          <Link to={props.more} className="text-xs text-primary hover:underline">Ver todos</Link>
        )}
      </CardHeader>
      <CardContent>
        {props.players.length === 0 ? (
          <p className="text-sm text-muted-foreground">{props.empty ?? "Sem dados."}</p>
        ) : (
          <ol className="space-y-0.5">
            {props.players.map((p, i) => (
              <li key={p.player_id}>
                <Link to={`/jogador/${p.player_id}`} className="flex items-center gap-2 rounded-md px-1 py-1 hover:bg-muted">
                  <span className="w-4 text-right text-xs tabular-nums text-muted-foreground">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{p.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {p.age ?? "—"} anos · {p.positions.map((x) => POSITION_LABEL[x] ?? x).join(" ")} · {p.club ?? "Sem clube"}
                    </span>
                  </span>
                  {props.right(p)}
                </Link>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
