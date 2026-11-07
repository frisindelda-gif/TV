import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, SlidersHorizontal, Plus, RotateCcw, Search, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getJson, type FilterOptions, type PlayerPage } from "@/api";
import { AbilityPill, EmptyState, ErrorBox, QualityIcon } from "@/components/common";
import { POSITION_LABEL } from "@/components/PositionPitch";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { METRIC_GROUP_LABEL, fmtDate, fmtInt, fmtMetric, fmtMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;
const TEXT_KEYS = ["q", "club", "nationality", "position", "position_group", "min_age", "max_age", "min_ca", "min_pa", "max_value", "expires_before", "quality", "min_minutes", "min_ca_delta", "new_only"] as const;
type TextKey = (typeof TEXT_KEYS)[number];
type MetricFilter = { key: string; min: string; kind: "m" | "p" };
type Draft = Record<TextKey, string> & { attrs: { key: string; min: string }[]; metrics: MetricFilter[] };

const CATEGORY_LABEL: Record<string, string> = {
  technical: "Técnicos", mental: "Mentais", physical: "Físicos", goalkeeping: "Guarda-redes",
  hidden: "Escondidos", personality: "Personalidade",
};

function draftFrom(params: URLSearchParams): Draft {
  const d = Object.fromEntries(TEXT_KEYS.map((k) => [k, params.get(k) ?? ""])) as Record<TextKey, string>;
  const attrs = params.getAll("min_attr").map((s) => {
    const [key, min] = s.split(":");
    return { key: key ?? "", min: min ?? "" };
  });
  const metrics: MetricFilter[] = [
    ...params.getAll("min_metric").map((s) => ({ key: s.split(":")[0] ?? "", min: s.split(":")[1] ?? "", kind: "m" as const })),
    ...params.getAll("min_percentile").map((s) => ({ key: s.split(":")[0] ?? "", min: s.split(":")[1] ?? "", kind: "p" as const })),
  ];
  return { ...d, attrs, metrics };
}

function addYear(iso: string | null): string {
  const d = iso ? new Date(`${iso}T00:00:00`) : new Date();
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

// Colunas base, crescimento ou "m:<métrica>" / "p:<métrica>" (percentil).
type SortKey = string;
const ASC_DEFAULT = new Set(["name", "club", "age", "contract_expires"]);

export default function PlayersPage() {
  const { careers, career, attributes, attrLabel, metrics: catalog, metricDef } = useCareer();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<Draft>(() => draftFrom(params));
  const [data, setData] = useState<PlayerPage | null>(null);
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false); // só relevante em ecrãs pequenos

  const sort: SortKey = params.get("sort") || "ca";
  const order = params.get("order") === "asc" ? "asc" : "desc";
  const page = Math.max(0, Number(params.get("page") ?? 0));

  useEffect(() => setDraft(draftFrom(params)), [params]);

  useEffect(() => {
    if (!career) return;
    getJson<FilterOptions>(`/api/filters?career_id=${career.id}`).then(setOptions).catch(() => setOptions(null));
  }, [career]);

  useEffect(() => {
    if (!career) return;
    const ctrl = new AbortController();
    const q = new URLSearchParams(params);
    q.delete("page");
    q.set("career_id", String(career.id));
    q.set("sort", sort);
    q.set("order", order);
    q.set("limit", String(PAGE_SIZE));
    q.set("offset", String(page * PAGE_SIZE));
    setLoading(true);
    getJson<PlayerPage>(`/api/players?${q}`, ctrl.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, [career, params, sort, order, page]);

  const apply = (d: Draft) => {
    const next = new URLSearchParams();
    for (const k of TEXT_KEYS) if (d[k].trim()) next.set(k, d[k].trim());
    for (const a of d.attrs) if (a.key && a.min) next.append("min_attr", `${a.key}:${a.min}`);
    for (const m of d.metrics)
      if (m.key && m.min) next.append(m.kind === "p" ? "min_percentile" : "min_metric", `${m.key}:${m.min.replace(",", ".")}`);
    if (params.get("sort")) next.set("sort", sort);
    if (params.get("order")) next.set("order", order);
    setParams(next);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    apply(draft);
    setShowFilters(false);
  };

  const setField = (k: TextKey, v: string, immediate = false) => {
    const d = { ...draft, [k]: v };
    setDraft(d);
    if (immediate) apply(d);
  };

  const quick = (preset: Partial<Record<TextKey, string>>, sortBy?: SortKey) => {
    const next = new URLSearchParams();
    for (const [k, v] of Object.entries(preset)) if (v) next.set(k, v);
    if (sortBy) {
      next.set("sort", sortBy);
      next.set("order", ASC_DEFAULT.has(sortBy) ? "asc" : "desc");
    }
    setParams(next);
  };

  const setSort = (key: SortKey) => {
    const next = new URLSearchParams(params);
    if (sort === key) next.set("order", order === "desc" ? "asc" : "desc");
    else {
      next.set("sort", key);
      next.set("order", ASC_DEFAULT.has(key) ? "asc" : "desc");
    }
    next.delete("page");
    setParams(next);
  };

  const goPage = (p: number) => {
    const next = new URLSearchParams(params);
    if (p > 0) next.set("page", String(p));
    else next.delete("page");
    setParams(next);
    window.scrollTo({ top: 0 });
  };

  const activeCount = useMemo(
    () =>
      TEXT_KEYS.filter((k) => params.get(k)).length +
      params.getAll("min_attr").length +
      params.getAll("min_metric").length +
      params.getAll("min_percentile").length,
    [params],
  );

  if (careers === null) return <div className="text-sm text-muted-foreground">A carregar…</div>;
  if (career === null) {
    return (
      <EmptyState title="Ainda não há dados importados">
        Vá a <Link className="text-primary underline" to="/dados">Dados</Link> para importar um save, ler o jogo ou
        criar uma carreira de demonstração.
      </EmptyState>
    );
  }

  const metricOptions = Object.entries(METRIC_GROUP_LABEL).map(([g, label]) => (
    <optgroup key={g} label={label}>
      {catalog?.metrics
        .filter((m) => m.group === g && m.unit !== "minutes")
        .map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
    </optgroup>
  ));
  const metricKey = sort.startsWith("m:") || sort.startsWith("p:") ? sort.slice(2) : data?.items[0]?.metric_key ?? null;
  const metricCol = metricKey ? metricDef(metricKey) : undefined;
  const showGrowth = data?.items.some((p) => p.ca_delta !== null) ?? false;

  const grouped = attributes.reduce<Record<string, typeof attributes>>((acc, a) => {
    (acc[a.category] ??= []).push(a);
    return acc;
  }, {});

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-3">
        <Button variant="outline" className="w-full lg:hidden" onClick={() => setShowFilters((v) => !v)} aria-expanded={showFilters}>
          <SlidersHorizontal /> {showFilters ? "Esconder filtros" : "Filtros"}
          {activeCount > 0 && <span className="text-primary">({activeCount})</span>}
        </Button>
        <div className={cn("space-y-3", !showFilters && "hidden lg:block")}>
        <Card className="p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Filtros rápidos</div>
          <div className="flex flex-wrap gap-1.5">
            <QuickChip onClick={() => quick({ max_age: "19", min_pa: "150" })}>Wonderkids</QuickChip>
            <QuickChip onClick={() => quick({ max_age: "23", min_pa: "140", max_value: "2000000" })}>Potencial barato</QuickChip>
            <QuickChip onClick={() => quick({ expires_before: addYear(options?.game_date ?? null) })}>Contrato a terminar</QuickChip>
            <QuickChip onClick={() => quick({ min_ca: "150" })}>Elite (CA 150+)</QuickChip>
            <QuickChip onClick={() => quick({ quality: "error" })}>Leituras com erro</QuickChip>
          </div>
          <div className="mb-2 mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Métricas</div>
          <div className="flex flex-wrap gap-1.5">
            <QuickChip onClick={() => quick({}, "ca_delta")}>Maiores subidas</QuickChip>
            <QuickChip onClick={() => quick({ new_only: "true", max_age: "17" }, "pa")}>Novos regens</QuickChip>
            <QuickChip onClick={() => quick({ min_minutes: "900" }, "m:average_rating")}>Melhor nota</QuickChip>
            <QuickChip onClick={() => quick({ min_minutes: "900", position_group: "ST" }, "m:goals_90")}>Goleadores</QuickChip>
            <QuickChip onClick={() => quick({ min_minutes: "900", max_age: "21" }, "m:average_rating")}>Jovens em forma</QuickChip>
          </div>
        </Card>

        <Card className="p-3">
          <form onSubmit={onSubmit} className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Filtros {activeCount > 0 && <span className="text-primary">({activeCount})</span>}
              </div>
              {activeCount > 0 && (
                <Button type="button" variant="ghost" size="sm" onClick={() => quick({})}>
                  <RotateCcw /> Limpar
                </Button>
              )}
            </div>

            <div className="space-y-1">
              <Label htmlFor="f-q">Nome</Label>
              <Input id="f-q" value={draft.q} onChange={(e) => setField("q", e.target.value)} placeholder="Pesquisar nome…" />
            </div>

            <div className="space-y-1">
              <Label htmlFor="f-pos">Posição</Label>
              <Select id="f-pos" value={draft.position} onChange={(e) => setField("position", e.target.value, true)}>
                <option value="">Qualquer</option>
                {(options?.positions ?? Object.keys(POSITION_LABEL)).map((p) => (
                  <option key={p} value={p}>{POSITION_LABEL[p] ?? p} ({p})</option>
                ))}
              </Select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="f-club">Clube</Label>
              <Select id="f-club" value={draft.club} onChange={(e) => setField("club", e.target.value, true)}>
                <option value="">Qualquer</option>
                {options?.clubs.map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.players})</option>
                ))}
              </Select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="f-nat">Nacionalidade</Label>
              <Select id="f-nat" value={draft.nationality} onChange={(e) => setField("nationality", e.target.value, true)}>
                <option value="">Qualquer</option>
                {options?.nationalities.map((n) => (
                  <option key={n.name} value={n.name}>{n.name} ({n.players})</option>
                ))}
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <NumField id="f-amin" label="Idade mín." value={draft.min_age} onChange={(v) => setField("min_age", v)} />
              <NumField id="f-amax" label="Idade máx." value={draft.max_age} onChange={(v) => setField("max_age", v)} />
              <NumField id="f-ca" label="CA mín." value={draft.min_ca} onChange={(v) => setField("min_ca", v)} max={200} />
              <NumField id="f-pa" label="PA mín." value={draft.min_pa} onChange={(v) => setField("min_pa", v)} max={200} />
            </div>

            <NumField id="f-val" label="Valor máx. (£)" value={draft.max_value} onChange={(v) => setField("max_value", v)} step={100000} />

            <div className="space-y-1">
              <Label htmlFor="f-exp">Contrato termina até</Label>
              <Input id="f-exp" type="date" value={draft.expires_before} onChange={(e) => setField("expires_before", e.target.value)} />
            </div>

            <div className="space-y-1.5">
              <Label>Atributos (mínimo)</Label>
              {draft.attrs.map((a, i) => (
                <div key={i} className="flex gap-1.5">
                  <Select
                    aria-label="Atributo"
                    value={a.key}
                    onChange={(e) => {
                      const attrs = [...draft.attrs];
                      attrs[i] = { ...a, key: e.target.value };
                      setDraft({ ...draft, attrs });
                    }}
                  >
                    <option value="">Escolher…</option>
                    {Object.entries(grouped).map(([cat, list]) => (
                      <optgroup key={cat} label={CATEGORY_LABEL[cat] ?? cat}>
                        {list.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
                      </optgroup>
                    ))}
                  </Select>
                  <Input
                    aria-label="Valor mínimo"
                    className="w-16 shrink-0"
                    type="number"
                    min={1}
                    max={20}
                    value={a.min}
                    onChange={(e) => {
                      const attrs = [...draft.attrs];
                      attrs[i] = { ...a, min: e.target.value };
                      setDraft({ ...draft, attrs });
                    }}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    aria-label="Remover filtro"
                    onClick={() => setDraft({ ...draft, attrs: draft.attrs.filter((_, j) => j !== i) })}
                  >
                    <X />
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setDraft({ ...draft, attrs: [...draft.attrs, { key: "", min: "15" }] })}
              >
                <Plus /> Adicionar atributo
              </Button>
            </div>

            <div className="space-y-1.5 border-t pt-3">
              <Label>Desempenho</Label>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label htmlFor="f-grp" className="font-normal">Grupo de posição</Label>
                  <Select id="f-grp" value={draft.position_group} onChange={(e) => setField("position_group", e.target.value, true)}>
                    <option value="">Qualquer</option>
                    {Object.entries(catalog?.position_groups ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </Select>
                </div>
                <NumField id="f-min" label="Minutos mín." value={draft.min_minutes} onChange={(v) => setField("min_minutes", v)} step={90} />
              </div>
              {draft.metrics.map((m, i) => {
                const update = (patch: Partial<MetricFilter>) => {
                  const metrics = [...draft.metrics];
                  metrics[i] = { ...m, ...patch };
                  setDraft({ ...draft, metrics });
                };
                return (
                  <div key={i} className="space-y-1 rounded-md border p-1.5">
                    <div className="flex gap-1.5">
                      <Select aria-label="Métrica" value={m.key} onChange={(e) => update({ key: e.target.value })}>
                        <option value="">Escolher métrica…</option>
                        {metricOptions}
                      </Select>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        aria-label="Remover filtro de métrica"
                        onClick={() => setDraft({ ...draft, metrics: draft.metrics.filter((_, j) => j !== i) })}
                      >
                        <X />
                      </Button>
                    </div>
                    <div className="flex gap-1.5">
                      <Select aria-label="Tipo" value={m.kind} onChange={(e) => update({ kind: e.target.value as "m" | "p" })}>
                        <option value="p">Percentil ≥</option>
                        <option value="m">Valor ≥</option>
                      </Select>
                      <Input
                        aria-label="Mínimo"
                        className="w-20 shrink-0"
                        inputMode="decimal"
                        value={m.min}
                        onChange={(e) => update({ min: e.target.value })}
                      />
                    </div>
                  </div>
                );
              })}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setDraft({ ...draft, metrics: [...draft.metrics, { key: "", min: "75", kind: "p" }] })}
              >
                <Plus /> Adicionar métrica
              </Button>
              <p className="text-[11px] text-muted-foreground">
                Percentil compara com a mesma posição (≥{catalog?.min_minutes_for_percentile ?? 450} min). Só com dados do save.
              </p>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 accent-[hsl(var(--primary))]"
                  checked={draft.new_only === "true"}
                  onChange={(e) => setField("new_only", e.target.checked ? "true" : "", true)}
                />
                Só novos nesta importação
              </label>
              <NumField id="f-delta" label="CA ganho mín. (desde a anterior)" value={draft.min_ca_delta} onChange={(v) => setField("min_ca_delta", v)} />
            </div>

            <Button type="submit" className="w-full"><Search /> Pesquisar</Button>
          </form>
        </Card>
        </div>
      </aside>

      <section className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-lg font-semibold">Jogadores</h1>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <label className="flex items-center gap-1.5">
              Ordenar por
              <Select
                aria-label="Ordenar por"
                className="h-8 w-auto max-w-[220px]"
                value={sort}
                onChange={(e) => {
                  const next = new URLSearchParams(params);
                  next.set("sort", e.target.value);
                  next.set("order", ASC_DEFAULT.has(e.target.value) ? "asc" : "desc");
                  next.delete("page");
                  setParams(next);
                }}
              >
                <optgroup label="Jogador">
                  <option value="ca">CA</option>
                  <option value="pa">PA</option>
                  <option value="pa_gap">Margem de progressão (PA − CA)</option>
                  <option value="ca_delta">CA ganho desde a anterior</option>
                  <option value="age">Idade</option>
                  <option value="market_value">Valor</option>
                  <option value="wage_weekly">Salário</option>
                  <option value="contract_expires">Fim de contrato</option>
                  <option value="minutes">Minutos jogados</option>
                  <option value="name">Nome</option>
                </optgroup>
                {Object.entries(METRIC_GROUP_LABEL).map(([g, label]) => (
                  <optgroup key={g} label={`Métricas — ${label}`}>
                    {catalog?.metrics
                      .filter((m) => m.group === g && m.unit !== "minutes")
                      .map((m) => <option key={m.key} value={`m:${m.key}`}>{m.label}</option>)}
                  </optgroup>
                ))}
              </Select>
            </label>
            <span>{data ? `${data.total.toLocaleString("pt-PT")} resultados` : loading ? "A carregar…" : ""}</span>
          </div>
        </div>

        {params.getAll("min_attr").length > 0 && (
          <div className="flex flex-wrap gap-1.5 text-xs">
            {params.getAll("min_attr").map((s) => {
              const [k, v] = s.split(":");
              return <span key={s} className="rounded-full bg-accent px-2 py-0.5 text-accent-foreground">{attrLabel(k ?? "")} ≥ {v}</span>;
            })}
          </div>
        )}

        {(params.getAll("min_metric").length > 0 || params.getAll("min_percentile").length > 0) && (
          <div className="flex flex-wrap gap-1.5 text-xs">
            {params.getAll("min_metric").map((x) => {
              const [k, v] = x.split(":");
              return <span key={x} className="rounded-full bg-accent px-2 py-0.5 text-accent-foreground">{metricDef(k ?? "")?.label ?? k} ≥ {v}</span>;
            })}
            {params.getAll("min_percentile").map((x) => {
              const [k, v] = x.split(":");
              return <span key={x} className="rounded-full bg-accent px-2 py-0.5 text-accent-foreground">{metricDef(k ?? "")?.label ?? k}: percentil ≥ {v}</span>;
            })}
          </div>
        )}

        {error && <ErrorBox message={error} />}

        {/* Ecrãs pequenos: lista compacta com CA/PA sempre visíveis */}
        <Card className={cn("divide-y overflow-hidden sm:hidden", loading && "opacity-70")}>
          {data?.items.map((p) => (
            <Link key={p.player_id} to={`/jogador/${p.player_id}`} className="flex items-center gap-3 px-3 py-2.5 active:bg-muted">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 font-medium">
                  <span className="truncate">{p.name}</span>
                  {p.quality !== "ok" && <QualityIcon quality={p.quality} />}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {p.age ?? "—"} anos · {p.positions.map((x) => POSITION_LABEL[x] ?? x).join(" ")} · {p.club ?? "Sem clube"}
                </div>
                <div className="text-xs text-muted-foreground">
                  {metricCol && p.metric_value !== null
                    ? `${metricCol.label}: ${fmtMetric(p.metric_value, metricCol.unit)} · ${fmtInt(p.minutes)} min`
                    : `${fmtMoney(p.market_value)} · contrato ${fmtDate(p.contract_expires)}`}
                  {p.ca_delta ? <Delta v={p.ca_delta} className="ml-1.5" /> : null}
                </div>
              </div>
              <AbilityPill value={p.ca} />
              <AbilityPill value={p.pa} />
            </Link>
          ))}
          {data && data.items.length === 0 && (
            <div className="p-6 text-center text-sm text-muted-foreground">Nenhum jogador corresponde a estes filtros.</div>
          )}
        </Card>

        <Card className={cn("hidden overflow-hidden sm:block", loading && "opacity-70")}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <Th k="name" sort={sort} order={order} onSort={setSort} className="pl-4">Nome</Th>
                  <Th k="age" sort={sort} order={order} onSort={setSort}>Idade</Th>
                  <th className="px-2 py-2 font-medium">Pos.</th>
                  <th className="px-2 py-2 font-medium">Nac.</th>
                  <Th k="club" sort={sort} order={order} onSort={setSort}>Clube</Th>
                  <Th k="ca" sort={sort} order={order} onSort={setSort} align="center">CA</Th>
                  <Th k="pa" sort={sort} order={order} onSort={setSort} align="center">PA</Th>
                  {showGrowth && <Th k="ca_delta" sort={sort} order={order} onSort={setSort} align="right">Δ CA</Th>}
                  {metricCol && (
                    <>
                      <Th k={`m:${metricCol.key}`} sort={sort} order={order} onSort={setSort} align="right">{metricCol.label}</Th>
                      <Th k="minutes" sort={sort} order={order} onSort={setSort} align="right">Min.</Th>
                    </>
                  )}
                  <Th k="market_value" sort={sort} order={order} onSort={setSort} align="right">Valor</Th>
                  <Th k="wage_weekly" sort={sort} order={order} onSort={setSort} align="right">Salário/sem.</Th>
                  <Th k="contract_expires" sort={sort} order={order} onSort={setSort}>Contrato</Th>
                  <th className="w-8 px-2 py-2" aria-label="Qualidade da leitura" />
                </tr>
              </thead>
              <tbody>
                {data?.items.map((p) => (
                  <tr
                    key={p.player_id}
                    className="cursor-pointer border-b last:border-0 hover:bg-muted/60"
                    onClick={() => navigate(`/jogador/${p.player_id}`)}
                  >
                    <td className="py-2 pl-4 pr-2 font-medium">
                      <Link to={`/jogador/${p.player_id}`} className="hover:underline" onClick={(e) => e.stopPropagation()}>
                        {p.name}
                      </Link>
                    </td>
                    <td className="px-2 tabular-nums">{p.age ?? "—"}</td>
                    <td className="px-2 text-xs">
                      {p.positions.map((x) => (
                        <span key={x} className={cn("mr-1", p.natural_positions.includes(x) ? "font-semibold" : "text-muted-foreground")}>
                          {POSITION_LABEL[x] ?? x}
                        </span>
                      ))}
                    </td>
                    <td className="max-w-[110px] truncate px-2 text-xs text-muted-foreground">{p.nationalities.join(", ") || "—"}</td>
                    <td className="max-w-[180px] truncate px-2">{p.club ?? <span className="text-muted-foreground">Sem clube</span>}</td>
                    <td className="px-2 text-center"><AbilityPill value={p.ca} /></td>
                    <td className="px-2 text-center"><AbilityPill value={p.pa} /></td>
                    {showGrowth && <td className="px-2 text-right"><Delta v={p.ca_delta} /></td>}
                    {metricCol && (
                      <>
                        <td className="px-2 text-right font-medium tabular-nums">{fmtMetric(p.metric_value, metricCol.unit)}</td>
                        <td className="px-2 text-right tabular-nums text-muted-foreground">{fmtInt(p.minutes)}</td>
                      </>
                    )}
                    <td className="px-2 text-right tabular-nums">{fmtMoney(p.market_value)}</td>
                    <td className="px-2 text-right tabular-nums">{fmtMoney(p.wage_weekly)}</td>
                    <td className="whitespace-nowrap px-2 text-xs">{fmtDate(p.contract_expires)}</td>
                    <td className="px-2"><QualityIcon quality={p.quality} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data && data.items.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">Nenhum jogador corresponde a estes filtros.</div>
          )}
        </Card>

        {data && data.total > PAGE_SIZE && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total)} de {data.total.toLocaleString("pt-PT")}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => goPage(page - 1)}>
                <ChevronLeft /> Anterior
              </Button>
              <Button variant="outline" size="sm" disabled={(page + 1) * PAGE_SIZE >= data.total} onClick={() => goPage(page + 1)}>
                Seguinte <ChevronRight />
              </Button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function QuickChip({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border px-2.5 py-1 text-xs font-medium hover:border-primary hover:bg-accent hover:text-accent-foreground"
    >
      {children}
    </button>
  );
}

function NumField(props: { id: string; label: string; value: string; onChange: (v: string) => void; max?: number; step?: number }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={props.id}>{props.label}</Label>
      <Input
        id={props.id}
        type="number"
        inputMode="numeric"
        min={0}
        max={props.max}
        step={props.step}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      />
    </div>
  );
}

function Th(props: {
  k: SortKey;
  sort: SortKey;
  order: "asc" | "desc";
  onSort: (k: SortKey) => void;
  children: ReactNode;
  align?: "left" | "center" | "right";
  className?: string;
}) {
  const active = props.sort === props.k;
  return (
    <th
      className={cn("whitespace-nowrap px-2 py-2 font-medium", props.className)}
      aria-sort={active ? (props.order === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => props.onSort(props.k)}
        className={cn(
          "inline-flex items-center gap-0.5 hover:text-foreground",
          active && "text-foreground",
          props.align === "center" && "w-full justify-center",
          props.align === "right" && "w-full justify-end",
        )}
      >
        {props.children}
        {active && (props.order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
      </button>
    </th>
  );
}

function Delta({ v, className }: { v: number | null; className?: string }) {
  if (v === null || v === 0) return <span className={cn("text-muted-foreground tabular-nums", className)}>{v === 0 ? "0" : "—"}</span>;
  return (
    <span className={cn("whitespace-nowrap font-semibold tabular-nums", v > 0 ? "text-attr-good" : "text-attr-low", className)}>
      {v > 0 ? `▲ +${v}` : `▼ ${v}`}
    </span>
  );
}
