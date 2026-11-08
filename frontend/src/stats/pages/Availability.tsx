import { Check, X } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { postJson } from "@/api";
import { ErrorBox } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { cn } from "@/lib/utils";
import { STATUS_LABEL, type AvailabilityStatus } from "@/stats/api";
import { GROUP_ORDER, GROUP_SHORT, GroupSelect, StatusBadge } from "@/stats/components";
import { useStats } from "@/stats/context";
import { useStatsQuery } from "@/stats/useStatsQuery";

type Avail = { run_id: number; connector: string; catalog_size: number; counts: Record<AvailabilityStatus, number>;
  items: { metric: string; name: string; category: string; groups: string[]; status: AvailabilityStatus; reason: string;
    players_with_value: number; missing_fields: string[]; builtin: boolean }[] };
type Field = { raw_key: string; data_source: string | null; mapped_field: string | null; confidence: string | null; players_with_value: number;
  min_value: number | null; max_value: number | null; mean_value: number | null; integer_share: number | null };
type Proposal = { id: number; data_source: string; raw_key: string; status: string; created_metric_key: string | null;
  proposal: { name: string; meaning: string; meaning_source: string; unit: string; type: string; category: string; direction: string;
    per90: boolean; groups: string[]; equivalent_metric: string | null; equivalent_similarity: number | null; recommendation: string };
  sample: { players_with_value: number; min_value: number | null; max_value: number | null; mean_value: number | null } };

const ORDER: AvailabilityStatus[] = ["AVAILABLE", "CALCULABLE", "CUSTOM", "PARTIAL", "UNAVAILABLE", "INVALID"];

export default function StatsAvailability() {
  const { career } = useCareer();
  const { catalog, reloadCatalog, reloadAvailability } = useStats();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<"metrics" | "fields" | "proposals">("metrics");
  const [group, setGroup] = useState("");
  const [category, setCategory] = useState("");
  const [tick, setTick] = useState(0);
  const status = params.get("status") ?? "";
  const avail = useStatsQuery<Avail>(career ? `/api/stats/availability?career_id=${career.id}` : null, undefined, [tick]);
  const fields = useStatsQuery<Field[]>(career && tab === "fields" ? `/api/stats/fields?career_id=${career.id}` : null, undefined, [tick]);
  const props = useStatsQuery<Proposal[]>(tab === "proposals" ? "/api/stats/proposals" : null, undefined, [tick]);

  const items = (avail.data?.items ?? []).filter((i) => (!status || i.status === status) && (!group || i.groups.includes(group)) && (!category || i.category === category));
  const decide = async (p: Proposal, approveIt: boolean, overrides: Record<string, unknown> = {}) => {
    try {
      await postJson(`/api/stats/proposals/${p.id}/${approveIt ? "approve" : "reject"}`, approveIt ? overrides : undefined);
      await reloadCatalog();
      await reloadAvailability();
      setTick((t) => t + 1);
    } catch (e) {
      window.alert((e as Error).message);
    }
  };

  return (
    <div className="space-y-3">
      {avail.error && <ErrorBox message={avail.error} />}
      {avail.data && (
        <div className="flex flex-wrap gap-2">
          <div className="rounded-md border px-3 py-2 text-sm">Catálogo global: <b>{avail.data.catalog_size}</b> métricas</div>
          {ORDER.map((st) => (
            <button key={st} type="button" onClick={() => setParams(status === st ? {} : { status: st })}
              className={cn("flex items-center gap-2 rounded-md border px-3 py-2 text-sm", status === st && "border-primary bg-accent")}>
              <StatusBadge status={st} /><b className="tabular-nums">{avail.data!.counts[st] ?? 0}</b>
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-1.5" role="tablist">
        {([["metrics", "Métricas"], ["fields", "Campos do save"], ["proposals", "Novas métricas propostas"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} type="button" onClick={() => setTab(k)}
            className={cn("rounded-full border px-3 py-1.5 text-sm", tab === k ? "border-primary bg-accent text-accent-foreground" : "hover:bg-muted")}>{l}</button>
        ))}
      </div>

      {tab === "metrics" && (
        <Card>
          <CardHeader className="flex-wrap">
            <CardTitle>Disponibilidade neste save (importação #{avail.data?.run_id})</CardTitle>
            <div className="flex flex-wrap gap-2">
              <div className="w-48"><GroupSelect value={group} onChange={setGroup} /></div>
              <Select aria-label="Categoria" className="w-44" value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">Todas as categorias</option>
                {catalog && Object.entries(catalog.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Métrica</th><th className="font-medium">Estado</th><th className="font-medium">Posições</th><th className="text-right font-medium">Jogadores</th><th className="font-medium">Explicação</th></tr></thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.metric} className="border-t align-top">
                    <td className="py-1.5 pr-2"><div className="font-medium">{i.name}</div><div className="text-[11px] text-muted-foreground">{catalog?.categories[i.category] ?? i.category}{!i.builtin && " · personalizada"}</div></td>
                    <td className="pr-2"><StatusBadge status={i.status} /></td>
                    <td className="pr-2 text-xs text-muted-foreground">{i.groups.map((g) => GROUP_SHORT[g] ?? g).join(" ")}</td>
                    <td className="pr-2 text-right tabular-nums">{i.players_with_value || "—"}</td>
                    <td className="text-xs">{i.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {items.length === 0 && <p className="p-4 text-sm text-muted-foreground">Nenhuma métrica com estes filtros.</p>}
          </CardContent>
        </Card>
      )}

      {tab === "fields" && (
        <Card>
          <CardHeader><CardTitle>Campos estatísticos encontrados no save</CardTitle><span className="text-xs text-muted-foreground">"assumed" = correspondência pelo nome, por confirmar no FM27</span></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-sm">
              <thead className="text-left text-xs text-muted-foreground"><tr><th className="py-1 font-medium">Campo no save</th><th className="font-medium">Mapeado para</th><th className="font-medium">Confiança</th><th className="text-right font-medium">Jogadores</th><th className="text-right font-medium">Mín.</th><th className="text-right font-medium">Máx.</th><th className="text-right font-medium">Média</th></tr></thead>
              <tbody>
                {(fields.data ?? []).map((f) => (
                  <tr key={f.raw_key} className="border-t">
                    <td className="py-1 font-mono text-xs">{f.raw_key}</td>
                    <td className="text-xs">{f.mapped_field ? catalog?.fields[f.mapped_field]?.name ?? f.mapped_field : <span className="text-warning">não mapeado → proposta</span>}</td>
                    <td className="text-xs">{f.confidence ?? "—"}</td>
                    <td className="text-right tabular-nums">{f.players_with_value}</td>
                    <td className="text-right tabular-nums">{f.min_value?.toFixed(1) ?? "—"}</td>
                    <td className="text-right tabular-nums">{f.max_value?.toFixed(1) ?? "—"}</td>
                    <td className="text-right tabular-nums">{f.mean_value?.toFixed(2) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {tab === "proposals" && (
        <div className="grid gap-3 lg:grid-cols-2">
          {(props.data ?? []).map((p) => <ProposalCard key={p.id} p={p} onDecide={decide} />)}
          {props.data?.length === 0 && <p className="text-sm text-muted-foreground">Sem propostas: todos os campos do save estão mapeados.</p>}
        </div>
      )}
    </div>
  );
}

function ProposalCard({ p, onDecide }: { p: Proposal; onDecide: (p: Proposal, approve: boolean, o?: Record<string, unknown>) => void }) {
  const { catalog } = useStats();
  const [name, setName] = useState(p.proposal.name);
  const [category, setCategory] = useState(p.proposal.category);
  const [groups, setGroups] = useState<string[]>(p.proposal.groups);
  const [direction, setDirection] = useState(p.proposal.direction);
  const pending = p.status === "pending";
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle><span className="font-mono text-xs">{p.raw_key}</span> → {p.proposal.name}</CardTitle>
        <span className={cn("text-xs", p.status === "approved" ? "text-attr-good" : p.status === "rejected" ? "text-muted-foreground" : "text-warning")}>
          {p.status === "pending" ? "pendente" : p.status === "approved" ? `aprovada (${p.created_metric_key})` : "rejeitada"}</span>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p>{p.proposal.meaning} <span className="text-xs text-muted-foreground">({p.proposal.meaning_source === "known" ? "significado conhecido" : "inferido pelo nome"})</span></p>
        <p className="text-xs text-muted-foreground">Unidade: {p.proposal.unit} · tipo: {p.proposal.type} · {p.proposal.per90 ? "com valor por 90" : "sem valor por 90"} ·
          amostra: {p.sample.players_with_value} jogadores, {p.sample.min_value} – {p.sample.max_value}</p>
        <p className="text-xs">{p.proposal.equivalent_metric ? <>Equivalente possível no catálogo: <b>{catalog?.metrics.find((m) => m.id === p.proposal.equivalent_metric)?.name ?? p.proposal.equivalent_metric}</b>. </> : null}{p.proposal.recommendation}</p>
        {pending && (
          <div className="space-y-2 border-t pt-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1"><Label htmlFor={`pn-${p.id}`}>Nome</Label><Input id={`pn-${p.id}`} value={name} onChange={(e) => setName(e.target.value)} /></div>
              <div className="space-y-1"><Label htmlFor={`pc-${p.id}`}>Categoria</Label>
                <Select id={`pc-${p.id}`} value={category} onChange={(e) => setCategory(e.target.value)}>
                  {catalog && Object.entries(catalog.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select></div>
              <div className="space-y-1"><Label htmlFor={`pd-${p.id}`}>Direção</Label>
                <Select id={`pd-${p.id}`} value={direction} onChange={(e) => setDirection(e.target.value)}>
                  <option value="higher">Mais é melhor</option><option value="lower">Menos é melhor</option>
                </Select></div>
            </div>
            <div className="flex flex-wrap gap-1">
              {GROUP_ORDER.map((g) => (
                <button key={g} type="button" onClick={() => setGroups(groups.includes(g) ? groups.filter((x) => x !== g) : [...groups, g])}
                  className={cn("rounded-md border px-2 py-0.5 text-xs", groups.includes(g) ? "border-primary bg-accent text-accent-foreground" : "text-muted-foreground")}>{GROUP_SHORT[g]}</button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => onDecide(p, true, { name, category, groups, direction })}><Check /> Aprovar e adicionar ao catálogo</Button>
              <Button size="sm" variant="outline" onClick={() => onDecide(p, false)}><X /> Rejeitar</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export { STATUS_LABEL };
