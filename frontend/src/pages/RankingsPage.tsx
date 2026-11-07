import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getJson, postJson, type Rankings } from "@/api";
import { AbilityPill, EmptyState, ErrorBox } from "@/components/common";
import { ConfidenceBadge, ScoreBar, ScoreValue } from "@/components/evaluation/common";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { useEvaluation } from "@/lib/evaluation";
import { fmtMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE = 50;

export default function RankingsPage() {
  const { careers, career } = useCareer();
  const { catalog, active, posPt, roleName } = useEvaluation();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Rankings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recalc, setRecalc] = useState(false);
  const [tick, setTick] = useState(0);

  const group = params.get("group") ?? "ST";
  const sort = params.get("sort") ?? "score";
  const order = params.get("order") ?? "desc";
  const page = Number(params.get("page") ?? 0);
  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v === null || v === "" ? next.delete(k) : next.set(k, v));
    if (!("page" in patch)) next.delete("page");
    setParams(next);
  };

  useEffect(() => {
    if (!career) return;
    const ctrl = new AbortController();
    const q = new URLSearchParams(params);
    q.set("group", group);
    q.set("career_id", String(career.id));
    q.set("limit", String(PAGE));
    q.set("offset", String(page * PAGE));
    q.delete("page");
    setLoading(true);
    getJson<Rankings>(`/api/rankings?${q}`, ctrl.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message))
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [career, params, group, page, tick]);

  if (careers === null) return <div className="text-sm text-muted-foreground">A carregar…</div>;
  if (!career) return <EmptyState title="Ainda não há dados importados">Importe dados em <Link to="/dados" className="text-primary underline">Dados</Link>.</EmptyState>;

  const groupDef = catalog?.ranking_groups.find((g) => g.key === group);
  const groupRoles = (active?.spec.roles ?? []).filter((r) => r.enabled && r.positions.some((p) => groupDef?.positions.includes(p)));

  const doRecalc = async () => {
    setRecalc(true);
    try {
      await postJson("/api/evaluation/recalculate", { career_id: career.id });
      setTick((t) => t + 1);
    } finally {
      setRecalc(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-lg font-semibold">Rankings</h1>
        {data && (
          <span className="text-xs text-muted-foreground">
            Modelo: <Link to="/lab" className="text-primary hover:underline">{data.model.name}</Link>
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Grupo de posições">
        {catalog?.ranking_groups.map((g) => (
          <button
            key={g.key}
            role="tab"
            aria-selected={g.key === group}
            type="button"
            onClick={() => set({ group: g.key, sort: null, order: null })}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm font-medium",
              g.key === group ? "border-primary bg-accent text-accent-foreground" : "hover:bg-muted",
            )}
          >
            {g.label}
          </button>
        ))}
      </div>

      <Card className="flex flex-wrap items-end gap-3 p-3">
        <div className="space-y-1">
          <Label htmlFor="r-sort">Ordenar por</Label>
          <Select id="r-sort" className="w-56" value={sort} onChange={(e) => set({ sort: e.target.value, order: ["age", "name"].includes(e.target.value) ? "asc" : "desc" })}>
            <option value="score">Position Score ({groupDef?.positions.map(posPt).join("/")})</option>
            {groupDef && groupDef.positions.length > 1 &&
              groupDef.positions.map((p) => <option key={p} value={`position:${p}`}>Position Score {posPt(p)}</option>)}
            {groupRoles.length > 0 && (
              <optgroup label="Role Score">
                {groupRoles.map((r) => <option key={r.key} value={`role:${r.key}`}>{r.name}</option>)}
              </optgroup>
            )}
            <option value="best_role">Melhor função (qualquer)</option>
            <option value="ca">CA</option>
            <option value="pa">PA</option>
            <option value="age">Idade</option>
            <option value="market_value">Valor</option>
            <option value="ca_delta">CA ganho</option>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="r-order">Ordem</Label>
          <Select id="r-order" className="w-32" value={order} onChange={(e) => set({ order: e.target.value })}>
            <option value="desc">Decrescente</option>
            <option value="asc">Crescente</option>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="r-amin">Idade mín.</Label>
          <Input id="r-amin" type="number" className="w-20" defaultValue={params.get("min_age") ?? ""} onBlur={(e) => set({ min_age: e.target.value })} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="r-amax">Idade máx.</Label>
          <Input id="r-amax" type="number" className="w-20" defaultValue={params.get("max_age") ?? ""} onBlur={(e) => set({ max_age: e.target.value })} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="r-conf">Confiança mínima</Label>
          <Select id="r-conf" className="w-32" value={params.get("min_confidence") ?? ""} onChange={(e) => set({ min_confidence: e.target.value })}>
            <option value="">Qualquer</option>
            <option value="medium">Média</option>
            <option value="high">Alta</option>
          </Select>
        </div>
        <label className="flex h-9 items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-[hsl(var(--primary))]"
            checked={params.get("eligible_only") !== "false"}
            onChange={(e) => set({ eligible_only: e.target.checked ? null : "false" })}
          />
          Só competentes na posição
        </label>
        <span className="ml-auto text-sm text-muted-foreground">{data ? `${data.total.toLocaleString("pt-PT")} jogadores` : loading ? "A carregar…" : ""}</span>
      </Card>

      {data && data.state !== "fresh" && (
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          <AlertTriangle className="size-4" />
          {data.state === "missing" ? "Esta importação ainda não foi avaliada com o modelo ativo." : "Os pesos do modelo mudaram: os resultados estão desatualizados."}
          <Button size="sm" variant="outline" disabled={recalc} onClick={doRecalc}>{recalc ? "A recalcular…" : "Recalcular agora"}</Button>
        </div>
      )}
      {error && <ErrorBox message={error} />}

      <Card className={cn("overflow-hidden", loading && "opacity-70")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pl-4 pr-2 font-medium">#</th>
                <th className="px-2 font-medium">Nome</th>
                <th className="px-2 font-medium">Idade</th>
                <th className="px-2 font-medium">Clube</th>
                <th className="px-2 font-medium">Pos.</th>
                <th className="w-44 px-2 font-medium">Position Score</th>
                {data && data.positions.length > 1 && data.positions.map((p) => <th key={p} className="px-1 text-center font-medium">{posPt(p)}</th>)}
                {sort.startsWith("role:") && <th className="px-2 text-right font-medium">{roleName(sort.slice(5))}</th>}
                <th className="px-2 font-medium">Melhor função</th>
                <th className="px-2 text-center font-medium">CA</th>
                <th className="px-2 text-center font-medium">PA</th>
                <th className="px-2 text-right font-medium">Valor</th>
                <th className="px-2 font-medium">Confiança</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((x) => (
                <tr key={x.player_id} className="border-b last:border-0 hover:bg-muted/50">
                  <td className="py-2 pl-4 pr-2 tabular-nums text-muted-foreground">{x.rank}</td>
                  <td className="px-2 font-medium"><Link to={`/jogador/${x.player_id}`} className="hover:underline">{x.name}</Link></td>
                  <td className="px-2 tabular-nums">{x.age ?? "—"}</td>
                  <td className="max-w-[160px] truncate px-2">{x.club ?? "—"}</td>
                  <td className="px-2 text-xs">
                    {x.positions.map((p) => (
                      <span key={p} className={cn("mr-1", x.natural_positions.includes(p) ? "font-semibold" : "text-muted-foreground")}>{posPt(p)}</span>
                    ))}
                  </td>
                  <td className="px-2">
                    <div className="flex items-center gap-2">
                      <ScoreBar v={x.score} className="flex-1" />
                      <ScoreValue v={x.score} className="w-7 text-right" />
                    </div>
                  </td>
                  {data.positions.length > 1 &&
                    data.positions.map((p) => (
                      <td key={p} className={cn("px-1 text-center text-xs", !x.positions.includes(p) && "opacity-50")}>
                        <ScoreValue v={x.group_positions[p]} />
                      </td>
                    ))}
                  {sort.startsWith("role:") && <td className="px-2 text-right"><ScoreValue v={x.role_scores[sort.slice(5)]} /></td>}
                  <td className="max-w-[170px] truncate px-2 text-xs">
                    {x.best_role ? <>{roleName(x.best_role)} <ScoreValue v={x.best_role_score} className="ml-1" /></> : "—"}
                  </td>
                  <td className="px-2 text-center"><AbilityPill value={x.ca} /></td>
                  <td className="px-2 text-center"><AbilityPill value={x.pa} /></td>
                  <td className="px-2 text-right tabular-nums">{fmtMoney(x.market_value)}</td>
                  <td className="px-2"><ConfidenceBadge c={x.confidence} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && data.items.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">Nenhum jogador neste ranking com estes filtros.</div>}
      </Card>

      {data && data.total > PAGE && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{page * PAGE + 1}–{Math.min((page + 1) * PAGE, data.total)} de {data.total.toLocaleString("pt-PT")}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => set({ page: page > 1 ? String(page - 1) : null })}><ChevronLeft /> Anterior</Button>
            <Button variant="outline" size="sm" disabled={(page + 1) * PAGE >= data.total} onClick={() => set({ page: String(page + 1) })}>Seguinte <ChevronRight /></Button>
          </div>
        </div>
      )}
    </div>
  );
}
