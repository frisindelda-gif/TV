import { Download, Trash2, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { deleteJson, postJson } from "@/api";
import { AbilityPill } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtDateTime, fmtMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PlayerLink } from "@/stats/components";
import { useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

type Detail = { id: number; name: string; items: { player_id: number; name: string; age: number | null; club: string | null; ca: number | null;
  pa: number | null; market_value: number | null; note: string | null; source: string | null; added_at: string }[] };

export default function StatsShortlists() {
  const { shortlists, reloadShortlists } = useStats();
  const [sel, setSel] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const current = sel ?? shortlists[0]?.id ?? null;
  const { data } = useStatsQuery<Detail>(current ? `/api/stats/shortlists/${current}` : null, undefined, [tick]);

  const create = async () => {
    const name = window.prompt("Nome da shortlist");
    if (!name) return;
    const r = await postJson<{ id: number }>("/api/stats/shortlists", { name });
    await reloadShortlists();
    setSel(r.id);
  };
  const remove = async (pid: number) => {
    await deleteJson(`/api/stats/shortlists/${current}/items/${pid}`);
    setTick((t) => t + 1);
    await reloadShortlists();
  };
  const drop = async () => {
    if (!current || !window.confirm("Apagar esta shortlist?")) return;
    await deleteJson(`/api/stats/shortlists/${current}`);
    setSel(null);
    await reloadShortlists();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
      <Card className="h-fit p-2">
        {shortlists.map((s) => (
          <button key={s.id} type="button" onClick={() => setSel(s.id)}
            className={cn("flex w-full justify-between rounded px-2 py-1.5 text-left text-sm", s.id === current ? "bg-accent text-accent-foreground" : "hover:bg-muted")}>
            <span className="truncate">{s.name}</span><span className="text-xs text-muted-foreground">{s.players}</span>
          </button>
        ))}
        <Button variant="outline" size="sm" className="mt-2 w-full" onClick={() => void create()}>Nova shortlist</Button>
      </Card>
      {data ? (
        <Card>
          <CardHeader className="flex-wrap">
            <CardTitle>{data.name}</CardTitle>
            <div className="flex gap-2">
              <a href={`/api/stats/shortlists/${data.id}/export`}><Button size="sm" variant="outline"><Download /> CSV</Button></a>
              <Link to={`/stats/percentiles`}><Button size="sm" variant="outline">Usar como população</Button></Link>
              <Button size="sm" variant="ghost" onClick={() => void drop()}><Trash2 /> Apagar</Button>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {data.items.length === 0 ? <p className="text-sm text-muted-foreground">Vazia. Adicione jogadores a partir dos rankings, filtros, identificação ou mercado.</p> : (
              <table className="w-full min-w-[640px] text-sm">
                <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Jogador</th><th className="font-medium">Clube</th>
                  <th className="text-center font-medium">CA/PA</th><th className="text-right font-medium">Valor</th><th className="font-medium">Origem</th><th className="font-medium">Adicionado</th><th /></tr></thead>
                <tbody>
                  {data.items.map((it) => (
                    <tr key={it.player_id} className="border-t">
                      <td className="py-1.5"><PlayerLink id={it.player_id} name={it.name} /> <span className="text-xs text-muted-foreground">{it.age}</span></td>
                      <td>{it.club ?? "—"}</td><td className="whitespace-nowrap text-center"><AbilityPill value={it.ca} /> <AbilityPill value={it.pa} /></td>
                      <td className="text-right tabular-nums">{fmtMoney(it.market_value)}</td><td className="text-xs text-muted-foreground">{it.source ?? "—"}</td>
                      <td className="text-xs text-muted-foreground">{fmtDateTime(it.added_at)}</td>
                      <td><Button variant="ghost" size="icon" aria-label={`Remover ${it.name}`} onClick={() => void remove(it.player_id)}><X /></Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      ) : <p className="text-sm text-muted-foreground">Crie uma shortlist para começar.</p>}
    </div>
  );
}
