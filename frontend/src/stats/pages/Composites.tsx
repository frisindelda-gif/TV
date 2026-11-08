import { Copy, Lock, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { deleteJson, postJson, putJson } from "@/api";
import { ErrorBox } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { cn } from "@/lib/utils";
import type { Composite, SearchRequest, SearchResponse } from "@/stats/api";
import { DEFAULT_UNIVERSE, GroupSelect, MetricSelect, PlayerLink, posPt } from "@/stats/components";
import { useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

export default function StatsComposites() {
  const { career } = useCareer();
  const { composites, reloadComposites, label } = useStats();
  const [sel, setSel] = useState<number | null>(null);
  const current = composites.find((c) => c.id === sel) ?? composites[0];
  const [draft, setDraft] = useState<Composite | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (current) setDraft(structuredClone(current)); }, [current?.id, current?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = draft && current && JSON.stringify(draft) !== JSON.stringify(current);
  const ro = !!current?.builtin;

  const preview: SearchRequest | null = useMemo(() => current && career ? {
    career_id: career.id, scope: "club", filters: { group: current.group_key }, universe: DEFAULT_UNIVERSE,
    sort: { by: "composite", composite_id: current.id, order: "desc" }, columns: [], composite_ids: [current.id], limit: 10, offset: 0,
  } : null, [current, career]);
  const { data } = useStatsQuery<SearchResponse>(preview ? "/api/stats/search" : null, preview ?? undefined);

  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); setError(null); } catch (e) { setError((e as Error).message); }
  };
  const save = () => act(async () => { await putJson(`/api/stats/composites/${draft!.id}`, draft); await reloadComposites(); });
  const dup = () => act(async () => { const c = await postJson<Composite>(`/api/stats/composites/${current!.id}/duplicate`); await reloadComposites(); setSel(c.id); });
  const create = () => act(async () => {
    const name = window.prompt("Nome do novo modelo");
    if (!name) return;
    const c = await postJson<Composite>("/api/stats/composites", { name, group_key: "CM", components: [{ metric: "pass_pct", weight: 1, invert: false }], min_coverage: 0.6 });
    await reloadComposites(); setSel(c.id);
  });
  const remove = () => act(async () => { if (!window.confirm("Apagar este modelo?")) return; await deleteJson(`/api/stats/composites/${current!.id}`); setSel(null); await reloadComposites(); });
  const total = draft?.components.reduce((a, c) => a + (Number(c.weight) || 0), 0) ?? 0;

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
      <Card className="h-fit p-2">
        {composites.map((c) => (
          <button key={c.id} type="button" onClick={() => setSel(c.id)}
            className={cn("block w-full rounded px-2 py-1.5 text-left text-sm", c.id === current?.id ? "bg-accent text-accent-foreground" : "hover:bg-muted")}>
            {c.name}<span className="block text-[11px] text-muted-foreground">{c.group_label}{c.builtin ? " · inicial" : ""}</span>
          </button>
        ))}
        <Button variant="outline" size="sm" className="mt-2 w-full" onClick={() => void create()}><Plus /> Novo modelo</Button>
      </Card>
      {draft && current && (
        <div className="space-y-3">
          <Card>
            <CardHeader className="flex-wrap">
              <CardTitle className="flex items-center gap-2">{current.name} {ro && <Badge variant="secondary"><Lock className="size-3" /> modelo inicial, só de leitura</Badge>}</CardTitle>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => void dup()}><Copy /> Duplicar</Button>
                {!ro && <Button size="sm" variant="ghost" onClick={() => void remove()}><Trash2 /> Apagar</Button>}
                {!ro && <Button size="sm" disabled={!dirty} onClick={() => void save()}><Save /> Guardar</Button>}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Composite Score = Σ (percentil × peso) / Σ pesos das componentes com dados. Componentes sem dados ficam de fora (não penalizam);
                abaixo da cobertura mínima o score não é apresentado. É um indicador calculado, nunca uma estatística observada.
              </p>
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="space-y-1"><Label htmlFor="cs-name">Nome</Label><Input id="cs-name" disabled={ro} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></div>
                <div className="space-y-1"><Label htmlFor="cs-group">Posição avaliada</Label><GroupSelect id="cs-group" allowAll={false} value={draft.group_key} onChange={(v) => !ro && setDraft({ ...draft, group_key: v })} /></div>
                <div className="space-y-1"><Label htmlFor="cs-cov">Cobertura mínima (0,1–1)</Label>
                  <Input id="cs-cov" type="number" min={0.1} max={1} step={0.05} disabled={ro} value={draft.min_coverage} onChange={(e) => setDraft({ ...draft, min_coverage: Number(e.target.value) })} /></div>
              </div>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Componente</th><th className="w-24 font-medium">Peso</th><th className="w-16 text-right font-medium">Quota</th><th className="w-24 text-center font-medium">Inverter</th><th className="w-8" /></tr></thead>
                <tbody>
                  {draft.components.map((c, i) => (
                    <tr key={i} className="border-t">
                      <td className="py-1 pr-2">{ro ? label(c.metric) : (
                        <MetricSelect value={c.metric} group={draft.group_key} onlyComposite onlyPercentile
                          onChange={(v) => setDraft({ ...draft, components: draft.components.map((x, j) => (j === i ? { ...x, metric: v } : x)) })} />)}</td>
                      <td className="pr-2"><Input aria-label="Peso" type="number" min={0.1} step={0.5} disabled={ro} value={c.weight}
                        onChange={(e) => setDraft({ ...draft, components: draft.components.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)) })} /></td>
                      <td className="text-right tabular-nums text-muted-foreground">{total ? `${Math.round((100 * c.weight) / total)}%` : "—"}</td>
                      <td className="text-center"><input type="checkbox" aria-label="Inverter" disabled={ro} className="size-4 accent-[hsl(var(--primary))]" checked={c.invert}
                        onChange={(e) => setDraft({ ...draft, components: draft.components.map((x, j) => (j === i ? { ...x, invert: e.target.checked } : x)) })} /></td>
                      <td>{!ro && draft.components.length > 1 && <Button variant="ghost" size="icon" aria-label="Remover componente"
                        onClick={() => setDraft({ ...draft, components: draft.components.filter((_, j) => j !== i) })}><X /></Button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!ro && <Button size="sm" variant="outline" onClick={() => setDraft({ ...draft, components: [...draft.components, { metric: "", weight: 1, invert: false }] })}><Plus /> Componente</Button>}
              <p className="text-[11px] text-muted-foreground">Métricas em que menos é melhor (p.ex. perdas de bola, minutos por golo) já entram invertidas no percentil. "Inverter" acrescenta uma inversão manual.</p>
              {error && <ErrorBox message={error} />}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Top 10 nesta importação</CardTitle><span className="text-xs text-muted-foreground">com o modelo guardado</span></CardHeader>
            <CardContent>
              {data && data.items.filter((i) => i.composites[String(current.id)]?.score != null).length === 0 ? (
                <p className="text-sm text-muted-foreground">Ninguém atinge a cobertura mínima neste save (as componentes em falta aparecem em Metric Availability). Duplique e baixe a cobertura mínima, ou troque componentes.</p>
              ) : (
                <ol className="space-y-1 text-sm">
                  {data?.items.filter((i) => i.composites[String(current.id)]?.score != null).map((i, n) => {
                    const v = i.composites[String(current.id)];
                    return (
                      <li key={i.player_id} className="flex items-center gap-2">
                        <span className="w-4 text-xs text-muted-foreground">{n + 1}</span>
                        <span className="min-w-0 flex-1 truncate"><PlayerLink id={i.player_id} name={i.name} /> <span className="text-xs text-muted-foreground">{posPt(i.position)} · {i.club}</span></span>
                        <span className="text-[11px] text-muted-foreground">{Math.round((v.coverage ?? 0) * 100)}% dados</span>
                        <b className="w-8 text-right tabular-nums">{Math.round(v.score ?? 0)}</b>
                      </li>
                    );
                  })}
                </ol>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
