import { Copy, Lock, Plus, RefreshCw, RotateCcw, Save, Search, Star, Trash2, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteJson,
  getJson,
  postJson,
  putJson,
  type EvalModel,
  type EvalModelFull,
  type EvaluationSpec,
  type MetricCategory,
  type PlayerPage,
  type ScoreItem,
  type SpecMetricWeight,
} from "@/api";
import { ErrorBox } from "@/components/common";
import { ScoreValue } from "@/components/evaluation/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { CATEGORY_ORDER, useEvaluation } from "@/lib/evaluation";
import { cn } from "@/lib/utils";

type Tab = "metrics" | "positions" | "roles" | "settings";
type Preview = { name: string; positions: ScoreItem[]; roles: ScoreItem[]; metrics: ScoreItem[] };

function slugify(name: string, taken: Set<string>, prefix: string): string {
  const base =
    prefix +
    name
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 36);
  let key = /^[a-z]/.test(base) ? base : `m_${base}`;
  let i = 2;
  while (taken.has(key)) key = `${base}_${i++}`;
  return key;
}

function share(w: number, all: { weight: number }[]): string {
  const t = all.reduce((a, x) => a + (Number(x.weight) || 0), 0);
  return t > 0 ? `${Math.round((100 * (Number(w) || 0)) / t)}%` : "—";
}

export default function LabPage() {
  const { catalog, models, reload: reloadEval, posPt, posName } = useEvaluation();
  const { career, attrLabel } = useCareer();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [model, setModel] = useState<EvalModelFull | null>(null);
  const [draft, setDraft] = useState<EvaluationSpec | null>(null);
  const [tab, setTab] = useState<Tab>("metrics");
  const [sel, setSel] = useState<{ metric: string | null; position: string; role: string | null }>({ metric: null, position: "ST", role: null });
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<string | null>(null);

  const current = models.find((m) => m.id === selectedId) ?? models.find((m) => m.active) ?? models[0];
  const readOnly = !!model?.builtin;
  const dirty = useMemo(() => !!model && !!draft && JSON.stringify(model.spec) !== JSON.stringify(draft), [model, draft]);

  const loadModel = useCallback(async (id: number) => {
    const m = await getJson<EvalModelFull>(`/api/evaluation/models/${id}`);
    setModel(m);
    setDraft(structuredClone(m.spec));
    setSel((s) => ({ ...s, metric: s.metric && m.spec.metrics.some((x) => x.key === s.metric) ? s.metric : m.spec.metrics[0]?.key ?? null,
      role: s.role && m.spec.roles.some((x) => x.key === s.role) ? s.role : m.spec.roles[0]?.key ?? null }));
  }, []);

  useEffect(() => {
    if (current) void loadModel(current.id);
  }, [current?.id, loadModel]); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshState = useCallback(() => {
    if (!career || !current) return;
    getJson<{ state: string }>(`/api/evaluation/state?career_id=${career.id}&model_id=${current.id}`)
      .then((r) => setState(r.state))
      .catch(() => setState(null));
  }, [career, current]);
  useEffect(refreshState, [refreshState, model?.spec_hash]);

  const update = (fn: (d: EvaluationSpec) => void) => {
    if (!draft || readOnly) return;
    const d = structuredClone(draft);
    fn(d);
    setDraft(d);
  };

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const r = await fn();
      setInfo(typeof r === "string" ? r : label);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const save = () =>
    act("Modelo guardado.", async () => {
      const m = await putJson<EvalModelFull>(`/api/evaluation/models/${model!.id}`, { spec: draft, name: model!.name, description: model!.description });
      setModel(m);
      setDraft(structuredClone(m.spec));
      await reloadEval();
    });
  const duplicate = () =>
    act("Cópia criada. Pode editá-la à vontade.", async () => {
      if (dirty && !readOnly) await putJson(`/api/evaluation/models/${model!.id}`, { spec: draft });
      const m = await postJson<EvalModelFull>(`/api/evaluation/models/${model!.id}/duplicate`);
      await reloadEval();
      setSelectedId(m.id);
    });
  const activate = () =>
    act("Modelo ativo. Recalcule os rankings para o aplicar.", async () => {
      await postJson(`/api/evaluation/models/${model!.id}/activate`);
      await reloadEval();
    });
  const reset = () =>
    act("Pesos originais restaurados.", async () => {
      if (!window.confirm("Repor todos os pesos deste modelo com os valores originais?")) throw new Error("Cancelado.");
      const m = await postJson<EvalModelFull>(`/api/evaluation/models/${model!.id}/reset`);
      setModel(m);
      setDraft(structuredClone(m.spec));
      await reloadEval();
    });
  const remove = () =>
    act("Modelo apagado.", async () => {
      if (!window.confirm(`Apagar o modelo "${model!.name}"?`)) throw new Error("Cancelado.");
      await deleteJson(`/api/evaluation/models/${model!.id}`);
      setSelectedId(null);
      await reloadEval();
    });
  const recalc = () =>
    act("Rankings recalculados.", async () => {
      const r = await postJson<{ players: number; seconds: number }>("/api/evaluation/recalculate", { model_id: model!.id, career_id: career?.id });
      refreshState();
      return `Rankings recalculados: ${r.players.toLocaleString("pt-PT")} jogadores em ${r.seconds}s.`;
    });
  const rename = (patch: { name?: string; description?: string }) =>
    act("Nome guardado.", async () => {
      const m = await putJson<EvalModelFull>(`/api/evaluation/models/${model!.id}`, patch);
      setModel({ ...m, spec: model!.spec });
      await reloadEval();
    });

  if (!catalog || !model || !draft) return <div className="text-sm text-muted-foreground">A carregar o Position Lab…</div>;

  const metricNames = Object.fromEntries(draft.metrics.map((m) => [m.key, m.name]));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Position Lab</h1>
        <p className="text-sm text-muted-foreground">
          Métricas (atributos + pesos), modelos por posição e funções. As alterações só contam para os rankings depois de
          guardar e recalcular. {catalog.scale}.
        </p>
      </div>

      <Card className="space-y-3 p-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="lab-model">Modelo</Label>
            <Select
              id="lab-model"
              className="w-72"
              value={model.id}
              onChange={(e) => {
                if (dirty && !window.confirm("Há alterações por guardar. Descartar?")) return;
                setSelectedId(Number(e.target.value));
              }}
            >
              {models.map((m: EvalModel) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                  {m.active ? " ★ ativo" : ""}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 pb-1">
            {model.builtin && <Badge variant="secondary"><Lock className="size-3" /> original, só de leitura</Badge>}
            {model.active && <Badge><Star className="size-3" /> ativo</Badge>}
            {model.modified_from_original && <Badge variant="outline">alterado face ao original</Badge>}
            {dirty && <Badge variant="warning">alterações por guardar</Badge>}
            {state === "stale" && <Badge variant="warning">rankings desatualizados</Badge>}
            {state === "missing" && <Badge variant="warning">rankings por calcular</Badge>}
            <span className="text-[11px] text-muted-foreground" title="Identifica exatamente os pesos usados">hash {model.spec_hash}</span>
          </div>
          <div className="ml-auto flex flex-wrap gap-1.5">
            <Button variant="outline" size="sm" disabled={busy} onClick={duplicate}><Copy /> Duplicar</Button>
            {!model.active && <Button variant="outline" size="sm" disabled={busy || dirty} onClick={activate}><Star /> Ativar</Button>}
            {!readOnly && <Button variant="outline" size="sm" disabled={busy} onClick={reset}><RotateCcw /> Restaurar originais</Button>}
            {!readOnly && !model.active && <Button variant="outline" size="sm" disabled={busy} onClick={remove}><Trash2 /> Apagar</Button>}
            {dirty && <Button variant="ghost" size="sm" disabled={busy} onClick={() => setDraft(structuredClone(model.spec))}><Undo2 /> Descartar</Button>}
            {!readOnly && <Button size="sm" disabled={busy || !dirty} onClick={save}><Save /> Guardar</Button>}
            <Button variant="secondary" size="sm" disabled={busy || dirty || !career} onClick={recalc}><RefreshCw /> Recalcular rankings</Button>
          </div>
        </div>
        {readOnly ? (
          <p className="text-sm text-muted-foreground">
            O modelo original não pode ser alterado (garante que pode sempre voltar atrás). Use <b>Duplicar</b> para criar uma versão editável.
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-[260px_minmax(0,1fr)]">
            <Input aria-label="Nome do modelo" defaultValue={model.name} key={`n${model.id}`} onBlur={(e) => e.target.value !== model.name && rename({ name: e.target.value })} />
            <Input aria-label="Descrição" placeholder="Descrição (opcional)" defaultValue={model.description ?? ""} key={`d${model.id}`}
              onBlur={(e) => e.target.value !== (model.description ?? "") && rename({ description: e.target.value })} />
          </div>
        )}
        {error && <ErrorBox message={error} />}
        {info && <div className="text-sm text-attr-good">{info}</div>}
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap gap-1.5" role="tablist">
            {([["metrics", `Métricas (${draft.metrics.length})`], ["positions", "Posições (12)"], ["roles", `Funções (${draft.roles.length})`], ["settings", "Definições"]] as [Tab, string][]).map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} type="button" onClick={() => setTab(k)}
                className={cn("rounded-full border px-3 py-1.5 text-sm font-medium", tab === k ? "border-primary bg-accent text-accent-foreground" : "hover:bg-muted")}>
                {label}
              </button>
            ))}
          </div>

          {tab === "metrics" && (
            <MetricsTab draft={draft} readOnly={readOnly} selected={sel.metric} onSelect={(k) => setSel({ ...sel, metric: k })}
              update={update} catalog={catalog} attrLabel={attrLabel} posPt={posPt} />
          )}
          {tab === "positions" && (
            <Card>
              <CardHeader className="flex-wrap">
                <div className="flex flex-wrap gap-1">
                  {catalog.positions.map((p) => (
                    <button key={p.key} type="button" onClick={() => setSel({ ...sel, position: p.key })} title={p.name}
                      className={cn("rounded-md border px-2 py-1 text-xs font-semibold", sel.position === p.key ? "border-primary bg-accent text-accent-foreground" : "hover:bg-muted")}>
                      {p.pt}
                    </button>
                  ))}
                </div>
                {!readOnly && (
                  <Select aria-label="Copiar pesos de" className="h-8 w-auto" value="" onChange={(e) => {
                    const from = e.target.value;
                    update((d) => { d.positions.find((p) => p.key === sel.position)!.metrics = structuredClone(d.positions.find((p) => p.key === from)!.metrics); });
                  }}>
                    <option value="">Copiar pesos de…</option>
                    {catalog.positions.filter((p) => p.key !== sel.position).map((p) => <option key={p.key} value={p.key}>{p.pt} — {p.name}</option>)}
                  </Select>
                )}
              </CardHeader>
              <CardContent>
                <div className="mb-2 text-sm font-medium">{posName(sel.position)} ({posPt(sel.position)})</div>
                <WeightTable
                  rows={draft.positions.find((p) => p.key === sel.position)!.metrics}
                  options={draft.metrics.map((m) => ({ key: m.key, label: m.name, group: catalog.categories[m.category] }))}
                  readOnly={readOnly}
                  onChange={(rows) => update((d) => { d.positions.find((p) => p.key === sel.position)!.metrics = rows; })}
                  names={metricNames}
                />
              </CardContent>
            </Card>
          )}
          {tab === "roles" && (
            <RolesTab draft={draft} readOnly={readOnly} selected={sel.role} onSelect={(k) => setSel({ ...sel, role: k })}
              update={update} catalog={catalog} metricNames={metricNames} />
          )}
          {tab === "settings" && (
            <Card>
              <CardHeader><CardTitle>Definições do modelo</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="space-y-1">
                  <Label htmlFor="mincov">Cobertura mínima para calcular (0,1 – 1)</Label>
                  <Input id="mincov" type="number" min={0.1} max={1} step={0.05} className="w-28" disabled={readOnly} value={draft.min_coverage}
                    onChange={(e) => update((d) => { d.min_coverage = Number(e.target.value); })} />
                  <p className="text-xs text-muted-foreground">
                    Percentagem do peso que tem de estar disponível. Abaixo disso a métrica, posição ou função fica por calcular,
                    em vez de assumir zeros para os dados em falta.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <PreviewPanel draft={draft} tab={tab} sel={sel} />
      </div>
      <p className="text-xs text-muted-foreground">
        Pesos documentados em <code>docs/07-PESOS.md</code>. Volte aos <Link to="/rankings" className="text-primary hover:underline">Rankings</Link> depois de recalcular.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- métricas

function MetricsTab(props: {
  draft: EvaluationSpec;
  readOnly: boolean;
  selected: string | null;
  onSelect: (k: string) => void;
  update: (fn: (d: EvaluationSpec) => void) => void;
  catalog: NonNullable<ReturnType<typeof useEvaluation>["catalog"]>;
  attrLabel: (k: string) => string;
  posPt: (k: string) => string;
}) {
  const { draft, readOnly, selected, onSelect, update, catalog, attrLabel, posPt } = props;
  const [filter, setFilter] = useState("");
  const m = draft.metrics.find((x) => x.key === selected) ?? draft.metrics[0];
  const idx = draft.metrics.findIndex((x) => x.key === m.key);
  const usedBy = [
    ...draft.positions.filter((p) => p.metrics.some((w) => w.metric === m.key)).map((p) => posPt(p.key)),
    ...draft.roles.filter((r) => r.metrics.some((w) => w.metric === m.key)).map((r) => r.name),
  ];
  const total = m.attributes.reduce((a, x) => a + (Number(x.weight) || 0), 0);
  const formula = `(${m.attributes.map((a) => `${a.weight}×${a.invert ? `(100 − n(${a.attribute}))` : `n(${a.attribute})`}`).join(" + ")}) / ${total}`;

  const addMetric = () => {
    const name = window.prompt("Nome da nova métrica");
    if (!name) return;
    const key = slugify(name, new Set(draft.metrics.map((x) => x.key)), "custom_");
    update((d) => {
      d.metrics.push({ key, name, description: "", category: "technical", positions: [], attributes: [{ attribute: "passing", weight: 1, invert: false }] });
    });
    onSelect(key);
  };

  return (
    <div className="grid gap-3 md:grid-cols-[230px_minmax(0,1fr)]">
      <Card className="p-2">
        <div className="relative mb-2">
          <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
          <Input aria-label="Procurar métrica" className="pl-7" placeholder="Procurar…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="max-h-[560px] space-y-2 overflow-y-auto">
          {CATEGORY_ORDER.map((cat) => {
            const list = draft.metrics.filter((x) => x.category === cat && x.name.toLowerCase().includes(filter.toLowerCase()));
            if (!list.length) return null;
            return (
              <div key={cat}>
                <div className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{catalog.categories[cat]}</div>
                {list.map((x) => (
                  <button key={x.key} type="button" onClick={() => onSelect(x.key)}
                    className={cn("block w-full truncate rounded px-2 py-1 text-left text-sm", x.key === m.key ? "bg-accent text-accent-foreground" : "hover:bg-muted")}>
                    {x.name}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
        {!readOnly && <Button variant="outline" size="sm" className="mt-2 w-full" onClick={addMetric}><Plus /> Nova métrica</Button>}
      </Card>

      <Card>
        <CardContent className="space-y-3 pt-4">
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_200px]">
            <div className="space-y-1">
              <Label htmlFor="m-name">Nome</Label>
              <Input id="m-name" disabled={readOnly} value={m.name} onChange={(e) => update((d) => { d.metrics[idx].name = e.target.value; })} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="m-cat">Categoria</Label>
              <Select id="m-cat" disabled={readOnly} value={m.category} onChange={(e) => update((d) => { d.metrics[idx].category = e.target.value as MetricCategory; })}>
                {CATEGORY_ORDER.map((c) => <option key={c} value={c}>{catalog.categories[c]}</option>)}
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="m-desc">Descrição</Label>
            <Input id="m-desc" disabled={readOnly} value={m.description} onChange={(e) => update((d) => { d.metrics[idx].description = e.target.value; })} />
          </div>
          <div className="space-y-1">
            <Label>Posições associadas <span className="font-normal">(nenhuma = todas)</span></Label>
            <div className="flex flex-wrap gap-1">
              {catalog.positions.map((p) => {
                const on = m.positions.includes(p.key);
                return (
                  <button key={p.key} type="button" disabled={readOnly} onClick={() => update((d) => {
                    const ps = d.metrics[idx].positions;
                    d.metrics[idx].positions = on ? ps.filter((x) => x !== p.key) : [...ps, p.key];
                  })} className={cn("rounded-md border px-2 py-0.5 text-xs", on ? "border-primary bg-accent text-accent-foreground" : "text-muted-foreground")}>
                    {p.pt}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <Label>Atributos e pesos</Label>
            <table className="mt-1 w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr><th className="py-1 font-medium">Atributo</th><th className="w-24 font-medium">Peso</th><th className="w-16 text-right font-medium">Quota</th><th className="w-20 text-center font-medium">Invertido</th><th className="w-8" /></tr>
              </thead>
              <tbody>
                {m.attributes.map((a, i) => (
                  <tr key={i} className="border-t">
                    <td className="py-1 pr-2">
                      <Select aria-label="Atributo" disabled={readOnly} value={a.attribute} onChange={(e) => update((d) => { d.metrics[idx].attributes[i].attribute = e.target.value; })}>
                        {["technical", "mental", "physical", "goalkeeping", "hidden", "personality"].map((cat) => (
                          <optgroup key={cat} label={cat}>
                            {catalog.attributes.filter((x) => x.category === cat).map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
                          </optgroup>
                        ))}
                      </Select>
                    </td>
                    <td className="pr-2"><Input aria-label="Peso" type="number" min={0.1} step={0.5} disabled={readOnly} value={a.weight}
                      onChange={(e) => update((d) => { d.metrics[idx].attributes[i].weight = Number(e.target.value); })} /></td>
                    <td className="text-right tabular-nums text-muted-foreground">{share(a.weight, m.attributes)}</td>
                    <td className="text-center"><input type="checkbox" aria-label="Invertido" className="size-4 accent-[hsl(var(--primary))]" disabled={readOnly} checked={a.invert}
                      onChange={(e) => update((d) => { d.metrics[idx].attributes[i].invert = e.target.checked; })} /></td>
                    <td>{!readOnly && m.attributes.length > 1 && (
                      <Button variant="ghost" size="icon" aria-label="Remover atributo" onClick={() => update((d) => { d.metrics[idx].attributes.splice(i, 1); })}><X /></Button>
                    )}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!readOnly && (
              <Button variant="outline" size="sm" className="mt-2" onClick={() => update((d) => {
                const usedA = new Set(d.metrics[idx].attributes.map((x) => x.attribute));
                const free = catalog.attributes.find((x) => !usedA.has(x.key));
                if (free) d.metrics[idx].attributes.push({ attribute: free.key, weight: 1, invert: false });
              })}><Plus /> Adicionar atributo</Button>
            )}
          </div>

          <div className="rounded-md bg-muted/50 p-2 text-xs">
            <div><b>Fórmula:</b> <code className="break-all">{formula}</code></div>
            <div className="mt-1 text-muted-foreground">n(a) = (a − 1) / 19 × 100 · atributos em falta não contam (a cobertura baixa em vez de contar zero).</div>
            <div className="mt-1"><b>Usada em:</b> {usedBy.length ? usedBy.join(", ") : <span className="text-muted-foreground">nenhuma posição ou função</span>}</div>
            <div className="mt-1 text-muted-foreground">
              Atributos: {m.attributes.map((a) => attrLabel(a.attribute)).join(", ")}
            </div>
          </div>

          {!readOnly && (
            <Button variant="ghost" size="sm" className="text-destructive" disabled={usedBy.length > 0} title={usedBy.length ? "Retire-a primeiro das posições e funções" : undefined}
              onClick={() => { update((d) => { d.metrics.splice(idx, 1); }); onSelect(draft.metrics[0].key); }}>
              <Trash2 /> Apagar métrica
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- funções

function RolesTab(props: {
  draft: EvaluationSpec;
  readOnly: boolean;
  selected: string | null;
  onSelect: (k: string) => void;
  update: (fn: (d: EvaluationSpec) => void) => void;
  catalog: NonNullable<ReturnType<typeof useEvaluation>["catalog"]>;
  metricNames: Record<string, string>;
}) {
  const { draft, readOnly, selected, onSelect, update, catalog, metricNames } = props;
  const r = draft.roles.find((x) => x.key === selected) ?? draft.roles[0];
  const idx = r ? draft.roles.findIndex((x) => x.key === r.key) : -1;

  const addRole = () => {
    const name = window.prompt("Nome da nova função (tem de existir no FM27 instalado)");
    if (!name) return;
    const key = slugify(name, new Set(draft.roles.map((x) => x.key)), "custom_");
    update((d) => {
      d.roles.push({ key, name, description: "", positions: ["MC"], metrics: [{ metric: d.metrics[0].key, weight: 1 }], enabled: true, availability: "unconfirmed" });
    });
    onSelect(key);
  };

  return (
    <div className="grid gap-3 md:grid-cols-[230px_minmax(0,1fr)]">
      <Card className="p-2">
        <div className="max-h-[560px] space-y-0.5 overflow-y-auto">
          {draft.roles.map((x) => (
            <button key={x.key} type="button" onClick={() => onSelect(x.key)}
              className={cn("flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-sm", x.key === r?.key ? "bg-accent text-accent-foreground" : "hover:bg-muted", !x.enabled && "opacity-50")}>
              <span className="truncate">{x.name}</span>
              <span className="shrink-0 text-[10px] text-muted-foreground">{x.positions.map((p) => catalog.positions.find((c) => c.key === p)?.pt).join("/")}</span>
            </button>
          ))}
        </div>
        {!readOnly && <Button variant="outline" size="sm" className="mt-2 w-full" onClick={addRole}><Plus /> Nova função</Button>}
      </Card>

      {r && (
        <Card>
          <CardContent className="space-y-3 pt-4">
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]" disabled={readOnly} checked={r.enabled}
                  onChange={(e) => update((d) => { d.roles[idx].enabled = e.target.checked; })} />
                Ativa (calcular e mostrar)
              </label>
              <Select aria-label="Disponibilidade" className="h-8 w-auto" disabled={readOnly} value={r.availability}
                onChange={(e) => update((d) => { d.roles[idx].availability = e.target.value as "confirmed" | "unconfirmed"; })}>
                <option value="unconfirmed">Por confirmar no FM27</option>
                <option value="confirmed">Confirmada no meu FM27</option>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="r-name">Nome</Label>
              <Input id="r-name" disabled={readOnly} value={r.name} onChange={(e) => update((d) => { d.roles[idx].name = e.target.value; })} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="r-desc">Descrição</Label>
              <Input id="r-desc" disabled={readOnly} value={r.description} onChange={(e) => update((d) => { d.roles[idx].description = e.target.value; })} />
            </div>
            <div className="space-y-1">
              <Label>Posições</Label>
              <div className="flex flex-wrap gap-1">
                {catalog.positions.map((p) => {
                  const on = r.positions.includes(p.key);
                  return (
                    <button key={p.key} type="button" disabled={readOnly || (on && r.positions.length === 1)} onClick={() => update((d) => {
                      const ps = d.roles[idx].positions;
                      d.roles[idx].positions = on ? ps.filter((x) => x !== p.key) : [...ps, p.key];
                    })} className={cn("rounded-md border px-2 py-0.5 text-xs", on ? "border-primary bg-accent text-accent-foreground" : "text-muted-foreground")}>
                      {p.pt}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <Label>Métricas e pesos</Label>
              <WeightTable rows={r.metrics} readOnly={readOnly} names={metricNames}
                options={draft.metrics.map((m) => ({ key: m.key, label: m.name, group: catalog.categories[m.category] }))}
                onChange={(rows) => update((d) => { d.roles[idx].metrics = rows; })} />
            </div>
            {!readOnly && (
              <Button variant="ghost" size="sm" className="text-destructive" onClick={() => { update((d) => { d.roles.splice(idx, 1); }); onSelect(draft.roles[0]?.key ?? ""); }}>
                <Trash2 /> Apagar função
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ----------------------------------------------------------- tabela de pesos

function WeightTable(props: {
  rows: SpecMetricWeight[];
  options: { key: string; label: string; group: string }[];
  readOnly: boolean;
  onChange: (rows: SpecMetricWeight[]) => void;
  names: Record<string, string>;
}) {
  const { rows, options, readOnly, onChange } = props;
  const groups = Array.from(new Set(options.map((o) => o.group)));
  const sorted = rows.map((r, i) => ({ r, i }));
  return (
    <div>
      <table className="mt-1 w-full text-sm">
        <thead className="text-left text-xs text-muted-foreground">
          <tr><th className="py-1 font-medium">Métrica</th><th className="w-24 font-medium">Peso</th><th className="w-16 text-right font-medium">Quota</th><th className="w-8" /></tr>
        </thead>
        <tbody>
          {sorted.map(({ r, i }) => (
            <tr key={i} className="border-t">
              <td className="py-1 pr-2">
                <Select aria-label="Métrica" disabled={readOnly} value={r.metric} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, metric: e.target.value } : x)))}>
                  {groups.map((g) => (
                    <optgroup key={g} label={g}>
                      {options.filter((o) => o.group === g).map((o) => (
                        <option key={o.key} value={o.key} disabled={o.key !== r.metric && rows.some((x) => x.metric === o.key)}>{o.label}</option>
                      ))}
                    </optgroup>
                  ))}
                </Select>
              </td>
              <td className="pr-2"><Input aria-label="Peso" type="number" min={0.1} step={1} disabled={readOnly} value={r.weight}
                onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, weight: Number(e.target.value) } : x)))} /></td>
              <td className="text-right tabular-nums text-muted-foreground">{share(r.weight, rows)}</td>
              <td>{!readOnly && rows.length > 1 && (
                <Button variant="ghost" size="icon" aria-label="Remover métrica" onClick={() => onChange(rows.filter((_, j) => j !== i))}><X /></Button>
              )}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!readOnly && (
        <Button variant="outline" size="sm" className="mt-2" onClick={() => {
          const free = options.find((o) => !rows.some((x) => x.metric === o.key));
          if (free) onChange([...rows, { metric: free.key, weight: 5 }]);
        }}><Plus /> Adicionar métrica</Button>
      )}
    </div>
  );
}

// ------------------------------------------------------------ pré-visualização

function PreviewPanel({ draft, tab, sel }: { draft: EvaluationSpec; tab: Tab; sel: { metric: string | null; position: string; role: string | null } }) {
  const { career } = useCareer();
  const { posPt } = useEvaluation();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<PlayerPage["items"]>([]);
  const [player, setPlayer] = useState<{ id: number; name: string } | null>(null);
  const [res, setRes] = useState<Preview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!career || player) return;
    getJson<PlayerPage>(`/api/players?career_id=${career.id}&limit=1`).then((p) => p.items[0] && setPlayer({ id: p.items[0].player_id, name: p.items[0].name })).catch(() => {});
  }, [career, player]);

  useEffect(() => {
    if (!career || q.length < 2) return setHits([]);
    const t = setTimeout(() => {
      getJson<PlayerPage>(`/api/players?career_id=${career.id}&q=${encodeURIComponent(q)}&limit=8`).then((p) => setHits(p.items)).catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, career]);

  useEffect(() => {
    if (!player) return;
    const t = setTimeout(() => {
      postJson<Preview>("/api/evaluation/preview", { spec: draft, player_id: player.id })
        .then((r) => { setRes(r); setErr(null); })
        .catch((e: Error) => setErr(e.message));
    }, 350);
    return () => clearTimeout(t);
  }, [draft, player]);

  const highlight = tab === "positions" ? sel.position : tab === "roles" ? sel.role : tab === "metrics" ? sel.metric : null;
  const list = (title: string, items: ScoreItem[], label: (x: ScoreItem) => string, n = 6) => {
    const shown = items.slice(0, n);
    const extra = highlight && !shown.some((x) => x.key === highlight) ? items.find((x) => x.key === highlight) : undefined;
    return (
      <div>
        <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
        <ul className="space-y-0.5 text-sm">
          {[...shown, ...(extra ? [extra] : [])].map((x) => (
            <li key={x.key} className={cn("flex justify-between gap-2 rounded px-1", x.key === highlight && "bg-accent text-accent-foreground")}>
              <span className="truncate">{label(x)}</span>
              <ScoreValue v={x.score} />
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <Card className="h-fit xl:sticky xl:top-28">
      <CardHeader><CardTitle>Pré-visualização</CardTitle><span className="text-xs text-muted-foreground">com os pesos atuais, mesmo por guardar</span></CardHeader>
      <CardContent className="space-y-3">
        <div className="relative">
          <Input aria-label="Procurar jogador" placeholder="Procurar jogador…" value={q} onChange={(e) => setQ(e.target.value)} />
          {hits.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full rounded-md border bg-card shadow">
              {hits.map((h) => (
                <li key={h.player_id}>
                  <button type="button" className="w-full px-2 py-1 text-left text-sm hover:bg-muted" onClick={() => { setPlayer({ id: h.player_id, name: h.name }); setQ(""); setHits([]); }}>
                    {h.name} <span className="text-xs text-muted-foreground">{h.age} · CA {h.ca}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {player ? <div className="text-sm font-medium"><Link className="hover:underline" to={`/jogador/${player.id}`}>{player.name}</Link></div>
          : <p className="text-sm text-muted-foreground">Importe dados para pré-visualizar.</p>}
        {err && <ErrorBox message={err} />}
        {res && !err && (
          <>
            {list("Posições", res.positions, (x) => `${posPt(x.key)} — ${x.name}`, 5)}
            {list("Funções", res.roles, (x) => x.name, 5)}
            {tab === "metrics" && sel.metric && list("Métrica em edição", res.metrics.filter((m) => m.key === sel.metric), (x) => x.name, 1)}
          </>
        )}
      </CardContent>
    </Card>
  );
}
