import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { CatalogMetric } from "@/stats/api";
import { GROUP_SHORT } from "@/stats/components";
import { useStats } from "@/stats/context";

const TYPE_LABEL: Record<string, string> = { count: "contagem", percentage: "percentagem", ratio: "rácio", derived_count: "derivada", value: "valor" };

export default function StatsCatalog() {
  const { catalog, metric, label } = useStats();
  const [mode, setMode] = useState<"position" | "category">("position");
  const [group, setGroup] = useState("CB");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const filtered = useMemo(() => (catalog?.metrics ?? []).filter((m) => !q || `${m.name} ${m.alt_name ?? ""} ${m.id}`.toLowerCase().includes(q.toLowerCase())), [catalog, q]);
  if (!catalog) return <div className="text-sm text-muted-foreground">A carregar…</div>;
  const selected = sel ? metric(sel) : undefined;
  const g = catalog.groups.find((x) => x.key === group);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Select aria-label="Organização" className="w-48" value={mode} onChange={(e) => setMode(e.target.value as "position" | "category")}>
            <option value="position">Por posição</option><option value="category">Por categoria</option>
          </Select>
          {mode === "position" && (
            <div className="flex flex-wrap gap-1">
              {[...catalog.groups.map((x) => x.key), "ALL"].map((k) => (
                <button key={k} type="button" onClick={() => setGroup(k)} className={cn("rounded-md border px-2 py-1 text-xs font-semibold",
                  group === k ? "border-primary bg-accent text-accent-foreground" : "hover:bg-muted")}>{k === "ALL" ? "Transversais" : GROUP_SHORT[k]}</button>
              ))}
            </div>
          )}
          <Input aria-label="Procurar métrica" placeholder="Procurar…" className="w-56" value={q} onChange={(e) => setQ(e.target.value)} />
          <span className="text-xs text-muted-foreground">{catalog.metrics.length} métricas · {catalog.views.length} vistas (total e /90)</span>
        </div>
        {mode === "position" && !q ? (
          <div className="grid gap-3 md:grid-cols-2">
            {(group === "ALL" ? catalog.transversal : g?.sections ?? []).map((s) => (
              <Card key={s.title}>
                <CardHeader><CardTitle>{s.title}</CardTitle><span className="text-xs text-muted-foreground">{s.items.length}</span></CardHeader>
                <CardContent>
                  <ul className="text-sm">
                    {s.items.map((k) => (
                      <li key={k}><button type="button" onClick={() => setSel(k.split("@")[0])}
                        className={cn("flex w-full justify-between gap-2 rounded px-1 py-0.5 text-left hover:bg-muted", sel === k.split("@")[0] && "bg-accent")}>
                        <span>{label(k)}</span><Flags m={metric(k.split("@")[0])} p90={k.endsWith("@p90")} /></button></li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(catalog.categories).map(([cat, cl]) => {
              const list = filtered.filter((m) => m.category === cat);
              if (!list.length) return null;
              return (
                <Card key={cat}>
                  <CardHeader><CardTitle>{cl}</CardTitle><span className="text-xs text-muted-foreground">{list.length}</span></CardHeader>
                  <CardContent><ul className="text-sm">{list.map((m) => (
                    <li key={m.id}><button type="button" onClick={() => setSel(m.id)} className={cn("flex w-full justify-between gap-2 rounded px-1 py-0.5 text-left hover:bg-muted", sel === m.id && "bg-accent")}>
                      <span>{m.name}</span><Flags m={m} /></button></li>
                  ))}</ul></CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
      <Card className="h-fit xl:sticky xl:top-28">
        {selected ? <Detail m={selected} /> : <CardContent className="pt-4 text-sm text-muted-foreground">Escolha uma métrica para ver a definição completa.</CardContent>}
      </Card>
    </div>
  );
}

function Flags({ m, p90 }: { m?: CatalogMetric; p90?: boolean }) {
  if (!m) return null;
  return (
    <span className="shrink-0 text-[10px] text-muted-foreground">
      {p90 ? "/90 " : ""}{m.direction === "lower" ? "↓ " : ""}{m.is_direct ? "direta" : "derivada"}{m.composed ? " · composta" : ""}{!m.builtin ? " · personalizada" : ""}
    </span>
  );
}

function Detail({ m }: { m: CatalogMetric }) {
  const { catalog } = useStats();
  const row = (k: string, v: React.ReactNode) => <><dt className="text-muted-foreground">{k}</dt><dd>{v}</dd></>;
  return (
    <>
      <CardHeader><CardTitle>{m.name}</CardTitle><span className="font-mono text-[11px] text-muted-foreground">{m.id}</span></CardHeader>
      <CardContent>
        <p className="mb-3 text-sm">{m.description}</p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          {row("Nome alternativo", m.alt_name ?? "—")}
          {row("Categoria", m.category_label)}
          {row("Tipo", TYPE_LABEL[m.type] ?? m.type)}
          {row("Unidade", m.unit)}
          {row("Posições", m.groups.map((g) => GROUP_SHORT[g] ?? g).join(", ") || "—")}
          {row("Por 90 minutos", m.per90 ? "sim" : "não")}
          {row("Percentil", m.percentile ? "sim" : "não")}
          {row("Direção", m.direction === "higher" ? "valores superiores são melhores" : "valores inferiores são melhores")}
          {row("Composite Scores", m.composite ? "pode ser usada" : "não")}
          {row("Indicador composto", m.composed ? "sim (soma de métricas diferentes)" : "não")}
          {row("Estado", m.validation_status === "custom" ? "personalizada (aprovada)" : "definida no catálogo; disponibilidade por save")}
          {row("Fonte", m.data_source)}
          {row("Elegibilidade", "minutos mínimos do universo de comparação (por defeito 450)")}
        </dl>
        <div className="mt-3 space-y-1 text-xs">
          <div className="font-semibold">Fórmula{m.formula_texts.length > 1 ? "s (por ordem de preferência)" : ""}</div>
          {m.formula_texts.map((f, i) => (
            <div key={i} className="rounded bg-muted/50 px-2 py-1">
              <code>{f}</code>
              <div className="text-[11px] text-muted-foreground">Campos: {m.source_fields[i].map((x) => catalog?.fields[x]?.name ?? x).join(", ")}</div>
            </div>
          ))}
          {m.per90 && <div className="text-muted-foreground">Por 90 = valor total / minutos × 90 (só com minutos válidos).</div>}
        </div>
      </CardContent>
    </>
  );
}
