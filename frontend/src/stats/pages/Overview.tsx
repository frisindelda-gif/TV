import { Link } from "react-router-dom";
import { ErrorBox } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCareer } from "@/lib/career";
import { fmtInt } from "@/lib/format";
import { STATUS_LABEL, type AvailabilityStatus, type StatPlayer } from "@/stats/api";
import { GROUP_ORDER, PlayerLink, StatusBadge, posPt } from "@/stats/components";
import { useStatsQuery } from "@/stats/useStatsQuery";

type OverviewData = {
  players_with_stats: number;
  eligible: number;
  availability: Partial<Record<AvailabilityStatus, number>>;
  catalog_size: number;
  groups: Record<string, { label: string; players: number; eligible: number }>;
  composites: { id: number; name: string; group: string; evaluated: number; mean_coverage: number | null;
    top: (StatPlayer & { score: number; coverage: number })[] }[];
  competitions: string[];
  universe: string;
  data_source: string | null;
};

export default function StatsOverview() {
  const { career } = useCareer();
  const { data, error } = useStatsQuery<OverviewData>(career ? `/api/stats/overview?career_id=${career.id}` : null);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <div className="text-sm text-muted-foreground">A carregar…</div>;
  if (data.players_with_stats === 0)
    return (
      <Card className="p-5 text-sm">
        A importação mais recente desta carreira não tem estatísticas de jogo (a leitura da memória não as inclui).
        Importe o save <b>.fm</b> em <Link to="/dados" className="text-primary underline">Dados</Link>. O catálogo continua
        completo em <Link to="/stats/catalog" className="text-primary underline">Metric Catalog</Link>.
      </Card>
    );
  const order: AvailabilityStatus[] = ["AVAILABLE", "CALCULABLE", "CUSTOM", "PARTIAL", "UNAVAILABLE", "INVALID"];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Jogadores com estatísticas" value={fmtInt(data.players_with_stats)} />
        <Tile label="Elegíveis (≥ 450 min)" value={fmtInt(data.eligible)} />
        <Tile label="Métricas no catálogo global" value={fmtInt(data.catalog_size)} to="/stats/catalog" />
        <Tile label="Utilizáveis neste save" to="/stats/availability"
          value={fmtInt((data.availability.AVAILABLE ?? 0) + (data.availability.CALCULABLE ?? 0) + (data.availability.CUSTOM ?? 0))} />
      </div>
      <Card>
        <CardHeader><CardTitle>Disponibilidade das métricas neste save</CardTitle>
          <span className="text-xs text-muted-foreground">fonte: {data.data_source ?? "—"}</span></CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {order.map((st) => (
            <Link key={st} to={`/stats/availability?status=${st}`} className="flex items-center gap-2 rounded-md border px-3 py-2 hover:bg-muted">
              <StatusBadge status={st} /> <span className="text-lg font-semibold tabular-nums">{data.availability[st] ?? 0}</span>
            </Link>
          ))}
          <p className="w-full text-xs text-muted-foreground">
            As métricas indisponíveis continuam no catálogo global; só não têm dados neste save. {STATUS_LABEL.CALCULABLE} = calculada a partir de outros campos.
          </p>
        </CardContent>
      </Card>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <Card>
          <CardHeader><CardTitle>Jogadores por posição</CardTitle></CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Posição</th><th className="text-right font-medium">Com estatísticas</th><th className="text-right font-medium">Elegíveis</th></tr></thead>
              <tbody>
                {GROUP_ORDER.map((g) => (
                  <tr key={g} className="border-t tabular-nums">
                    <td className="py-1.5"><Link to={`/stats/rankings?group=${g}`} className="hover:underline">{data.groups[g]?.label}</Link></td>
                    <td className="text-right">{fmtInt(data.groups[g]?.players)}</td>
                    <td className="text-right">{fmtInt(data.groups[g]?.eligible)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-muted-foreground">Competições: {data.competitions.join(", ")}</p>
          </CardContent>
        </Card>
        <div className="grid gap-3 sm:grid-cols-2">
          {data.composites.map((c) => (
            <Card key={c.id}>
              <CardHeader><CardTitle>{c.name}</CardTitle><span className="text-xs text-muted-foreground">Composite Score</span></CardHeader>
              <CardContent>
                {c.top.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Sem scores: cobertura média do modelo neste save {c.mean_coverage === null ? "—" : `${Math.round(c.mean_coverage * 100)}%`}
                    {" "}(abaixo do mínimo ou amostra insuficiente). <Link to="/stats/composites" className="text-primary underline">Ver modelo</Link>
                  </p>
                ) : (
                  <ol className="space-y-1 text-sm">
                    {c.top.map((p, i) => (
                      <li key={p.player_id} className="flex items-center gap-2">
                        <span className="w-4 text-xs text-muted-foreground">{i + 1}</span>
                        <span className="min-w-0 flex-1 truncate"><PlayerLink id={p.player_id} name={p.name} />
                          <span className="ml-1 text-xs text-muted-foreground">{posPt(p.position)} · {p.club}</span></span>
                        <span className="font-semibold tabular-nums">{Math.round(p.score)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Universo por defeito: {data.universe}.</p>
    </div>
  );
}

function Tile({ label, value, to }: { label: string; value: string; to?: string }) {
  const body = (
    <Card className="h-full p-3 hover:border-primary/50">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </Card>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}
