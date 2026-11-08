import { ChevronLeft, ChevronRight, Download } from "lucide-react";
import { useState } from "react";
import { AbilityPill } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { fmtMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SearchRequest, SearchResponse } from "@/stats/api";
import { AddToShortlist, GROUP_SHORT, Notes, PctCell, PlayerLink, posPt } from "@/stats/components";
import { fmtStat, useStats } from "@/stats/context";

export function ResultsTable({ req, data, loading, onPage, source }: {
  req: SearchRequest;
  data: SearchResponse | null;
  loading: boolean;
  onPage: (offset: number) => void;
  source: string;
}) {
  const { label, unit, metric } = useStats();
  const [sel, setSel] = useState<Set<number>>(new Set());
  const toggle = (id: number) => {
    const n = new Set(sel);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    setSel(n);
  };

  const exportCsv = async () => {
    const r = await fetch("/api/stats/search/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) });
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "statistical-scouting.csv";
    a.click();
  };

  if (!data) return <div className="text-sm text-muted-foreground">{loading ? "A calcular…" : ""}</div>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-muted-foreground">
          {data.total.toLocaleString("pt-PT")} jogadores · {data.scope_label} · universo: {data.universe}
        </span>
        <span className="flex flex-wrap items-center gap-2">
          <AddToShortlist playerIds={[...sel]} source={source} />
          <Button size="sm" variant="outline" onClick={() => void exportCsv()}><Download /> CSV</Button>
        </span>
      </div>
      <Notes notes={data.notes} />
      <Card className={cn("overflow-hidden", loading && "opacity-60")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                <th className="w-8 py-2 pl-3">
                  <input type="checkbox" aria-label="Selecionar todos" className="size-4 accent-[hsl(var(--primary))]"
                    checked={data.items.length > 0 && data.items.every((i) => sel.has(i.player_id))}
                    onChange={(e) => setSel(e.target.checked ? new Set(data.items.map((i) => i.player_id)) : new Set())} />
                </th>
                <th className="px-2 font-medium">#</th>
                <th className="px-2 font-medium">Jogador</th>
                <th className="px-2 font-medium">Idade</th>
                <th className="px-2 font-medium">Pos.</th>
                <th className="px-2 font-medium">Clube / competição</th>
                <th className="px-2 text-right font-medium">Min.</th>
                {req.columns.map((k) => {
                  const m = metric(k.split("@")[0]);
                  return (
                    <th key={k} className="px-2 font-medium" title={m?.description}>
                      {label(k)}
                      {m?.direction === "lower" && <span className="ml-0.5" title="menos é melhor">↓</span>}
                      {m?.composed && <span className="ml-1 text-[10px] text-warning" title="indicador composto">composto</span>}
                    </th>
                  );
                })}
                {data.composites.map((c) => <th key={c.id} className="px-2 font-medium" title="Composite Score (calculado)">{c.name}</th>)}
                <th className="px-2 text-center font-medium">CA/PA</th>
                <th className="px-2 text-right font-medium">Valor</th>
                <th className="px-2 text-right font-medium">Salário</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((it, n) => (
                <tr key={it.player_id} className="border-b last:border-0 hover:bg-muted/40">
                  <td className="py-1.5 pl-3">
                    <input type="checkbox" aria-label={`Selecionar ${it.name}`} className="size-4 accent-[hsl(var(--primary))]"
                      checked={sel.has(it.player_id)} onChange={() => toggle(it.player_id)} />
                  </td>
                  <td className="px-2 tabular-nums text-muted-foreground">{req.offset + n + 1}</td>
                  <td className="px-2"><PlayerLink id={it.player_id} name={it.name} /></td>
                  <td className="px-2 tabular-nums">{it.age ?? "—"}</td>
                  <td className="px-2 text-xs">{posPt(it.position)}</td>
                  <td className="max-w-[200px] px-2">
                    <div className="truncate">{it.club ?? "—"}</div>
                    <div className="truncate text-[11px] text-muted-foreground">{it.competition}</div>
                  </td>
                  <td className="px-2 text-right tabular-nums">{fmtStat(it.minutes, "minutes")}</td>
                  {req.columns.map((k) => {
                    const c = it.metrics[k];
                    const isP90 = k.endsWith("@p90");
                    return (
                      <td key={k} className="px-2">
                        <div className="flex items-center gap-2">
                          <span className="w-14 text-right font-medium tabular-nums" title={isP90 ? `Total: ${fmtStat(c?.total, "count")}` : undefined}>
                            {fmtStat(c?.value, unit(k))}
                          </span>
                          <PctCell p={c?.percentile} compact />
                        </div>
                        {c?.rank != null && (
                          <div className="text-[10px] text-muted-foreground">{c.rank}.º de {c.universe}{isP90 && c.total != null ? ` · total ${fmtStat(c.total, "count")}` : ""}</div>
                        )}
                      </td>
                    );
                  })}
                  {data.composites.map((cp) => {
                    const v = it.composites[String(cp.id)];
                    return (
                      <td key={cp.id} className="px-2">
                        <span className="font-semibold tabular-nums">{v?.score == null ? "—" : Math.round(v.score)}</span>
                        {v?.coverage != null && <span className="ml-1 text-[10px] text-muted-foreground">{Math.round(v.coverage * 100)}% dados</span>}
                      </td>
                    );
                  })}
                  <td className="whitespace-nowrap px-2 text-center"><AbilityPill value={it.ca} /> <AbilityPill value={it.pa} /></td>
                  <td className="px-2 text-right tabular-nums">{fmtMoney(it.market_value)}</td>
                  <td className="px-2 text-right tabular-nums">{fmtMoney(it.wage)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.items.length === 0 && <div className="p-6 text-center text-sm text-muted-foreground">Nenhum jogador cumpre estes critérios.</div>}
      </Card>
      {data.total > req.limit && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">{req.offset + 1}–{Math.min(req.offset + req.limit, data.total)} de {data.total}</span>
          <Button size="sm" variant="outline" disabled={req.offset === 0} onClick={() => onPage(Math.max(0, req.offset - req.limit))}><ChevronLeft /></Button>
          <Button size="sm" variant="outline" disabled={req.offset + req.limit >= data.total} onClick={() => onPage(req.offset + req.limit)}><ChevronRight /></Button>
        </div>
      )}
    </div>
  );
}

export function UniverseSummary({ data, columns }: { data: SearchResponse | null; columns: string[] }) {
  const { label, unit } = useStats();
  if (!data || !columns.length) return null;
  const k = columns[0];
  const parts = data.universe_summary[k] ?? [];
  if (!parts.length) return null;
  return (
    <Card className="overflow-x-auto p-3">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Universo de comparação — {label(k)}</div>
      <table className="w-full min-w-[640px] text-xs tabular-nums">
        <thead className="text-left text-muted-foreground">
          <tr><th className="py-1 font-medium">Competição</th><th className="font-medium">Posição</th><th className="text-right font-medium">Elegíveis</th><th className="text-right font-medium">Com valor</th><th className="text-right font-medium">Média</th><th className="text-right font-medium">Mediana</th><th className="text-right font-medium">Melhor</th><th className="text-right font-medium">Pior</th><th className="text-right font-medium">Cobertura</th></tr>
        </thead>
        <tbody>
          {parts.map((p) => (
            <tr key={p.partition} className="border-t">
              <td className="py-1">{p.competition}</td>
              <td>{GROUP_SHORT[p.position] ?? posPt(p.position)}</td>
              <td className="text-right">{p.eligible}</td>
              <td className="text-right">{p.with_value}{!p.sufficient && <span className="ml-1 text-warning" title="amostra insuficiente para percentis">!</span>}</td>
              <td className="text-right">{fmtStat(p.mean, unit(k))}</td>
              <td className="text-right">{fmtStat(p.median, unit(k))}</td>
              <td className="text-right">{fmtStat(p.best, unit(k))}</td>
              <td className="text-right">{fmtStat(p.worst, unit(k))}</td>
              <td className="text-right">{p.coverage == null ? "—" : `${Math.round(p.coverage * 100)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
