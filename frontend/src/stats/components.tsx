import { ListPlus } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { postJson } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { AvailabilityStatus, BaseFilters, UniverseIn } from "@/stats/api";
import { STATUS_LABEL } from "@/stats/api";
import { useStats } from "@/stats/context";

export const DEFAULT_UNIVERSE: UniverseIn = { competition: "same", position_level: "group", min_minutes: 450, min_sample: 10 };

export const GROUP_ORDER = ["GK", "CB", "FB", "DM", "CM", "WM", "AM", "W", "ST"];
export const GROUP_SHORT: Record<string, string> = {
  GK: "GR", CB: "DC", FB: "DD/DE", DM: "MDC", CM: "MC", WM: "MD/ME", AM: "MO", W: "AD/AE", ST: "PL",
};
const POS_PT: Record<string, string> = {
  GK: "GR", DR: "DD", DC: "DC", DL: "DE", DM: "MDC", MC: "MC", MR: "MD", ML: "ME", AMC: "MO", AMR: "AD", AML: "AE", ST: "PL",
};
export const posPt = (p: string | null | undefined) => (p ? POS_PT[p] ?? p : "—");

/** Seletor de métrica (vista total ou /90), agrupado por categoria; as do grupo de posição primeiro. */
export function MetricSelect(props: {
  value: string;
  onChange: (v: string) => void;
  group?: string | null;
  onlyPercentile?: boolean;
  onlyComposite?: boolean;
  ariaLabel?: string;
  className?: string;
  placeholder?: string;
}) {
  const { catalog, usable } = useStats();
  const options = useMemo(() => {
    if (!catalog) return [];
    const byCat: Record<string, { key: string; label: string; own: boolean; ok: boolean }[]> = {};
    for (const v of catalog.views) {
      const mid = v.key.split("@")[0];
      const m = catalog.metrics.find((x) => x.id === mid);
      if (!m) continue;
      if (props.onlyPercentile && !m.percentile) continue;
      if (props.onlyComposite && !m.composite) continue;
      const own = !props.group || m.groups.includes(props.group);
      (byCat[m.category] ??= []).push({ key: v.key, label: v.label, own, ok: usable(v.key) });
    }
    return Object.entries(byCat).map(([cat, list]) => ({
      cat,
      label: catalog.categories[cat] ?? cat,
      list: list.sort((a, b) => Number(b.ok) - Number(a.ok) || Number(b.own) - Number(a.own)),
    }));
  }, [catalog, props.group, props.onlyPercentile, props.onlyComposite, usable]);
  return (
    <Select aria-label={props.ariaLabel ?? "Métrica"} className={props.className} value={props.value} onChange={(e) => props.onChange(e.target.value)}>
      <option value="">{props.placeholder ?? "Escolher métrica…"}</option>
      {options.map((o) => (
        <optgroup key={o.cat} label={o.label}>
          {o.list.map((x) => (
            <option key={x.key} value={x.key}>
              {x.label}
              {!x.ok ? " — indisponível neste save" : ""}
              {props.group && !x.own ? " (fora do mapa da posição)" : ""}
            </option>
          ))}
        </optgroup>
      ))}
    </Select>
  );
}

export function GroupSelect({ value, onChange, allowAll = true, id }: { value: string; onChange: (v: string) => void; allowAll?: boolean; id?: string }) {
  const { catalog } = useStats();
  return (
    <Select id={id} aria-label="Posição" value={value} onChange={(e) => onChange(e.target.value)}>
      {allowAll && <option value="">Todas as posições</option>}
      {catalog?.groups.map((g) => <option key={g.key} value={g.key}>{g.label}</option>)}
    </Select>
  );
}

export function UniverseControls({ value, onChange }: { value: UniverseIn; onChange: (u: UniverseIn) => void }) {
  const { catalog, shortlists } = useStats();
  const opts = catalog?.min_minutes_options ?? [450, 900, 1350, 1800];
  const custom = !opts.includes(value.min_minutes);
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div className="space-y-1">
        <Label htmlFor="u-min">Minutos mínimos</Label>
        <div className="flex gap-1">
          <Select id="u-min" value={custom ? "custom" : String(value.min_minutes)}
            onChange={(e) => onChange({ ...value, min_minutes: e.target.value === "custom" ? value.min_minutes + 1 : Number(e.target.value) })}>
            {opts.map((o) => <option key={o} value={o}>{o}</option>)}
            <option value="custom">Personalizado</option>
          </Select>
          {custom && (
            <Input aria-label="Minutos personalizados" type="number" className="w-20" value={value.min_minutes}
              onChange={(e) => onChange({ ...value, min_minutes: Number(e.target.value) || 0 })} />
          )}
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor="u-comp">Comparar com</Label>
        <Select id="u-comp" value={value.competition} onChange={(e) => onChange({ ...value, competition: e.target.value as UniverseIn["competition"] })}>
          <option value="same">Mesma competição</option>
          <option value="all">Todas as competições</option>
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="u-pos">Posição de comparação</Label>
        <Select id="u-pos" value={value.position_level} onChange={(e) => onChange({ ...value, position_level: e.target.value as UniverseIn["position_level"] })}>
          <option value="group">Mesmo grupo de posição</option>
          <option value="position">Mesma posição exata</option>
          <option value="all">Todas as posições</option>
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="u-pop">População</Label>
        <Select id="u-pop" value={value.shortlist_id ?? ""} onChange={(e) => onChange({ ...value, shortlist_id: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Todos os jogadores</option>
          {shortlists.map((s) => <option key={s.id} value={s.id}>Shortlist: {s.name} ({s.players})</option>)}
        </Select>
      </div>
    </div>
  );
}

export function FiltersForm({ value, onChange, competitions = [], showGroup = true }: {
  value: BaseFilters;
  onChange: (f: BaseFilters) => void;
  competitions?: string[];
  showGroup?: boolean;
}) {
  const set = <K extends keyof BaseFilters>(k: K, v: BaseFilters[K] | "" | undefined) => {
    const next = { ...value };
    if (v === "" || v === undefined || (typeof v === "number" && Number.isNaN(v))) delete next[k];
    else next[k] = v as BaseFilters[K];
    onChange(next);
  };
  const num = (k: keyof BaseFilters, label: string, step?: number) => (
    <div className="space-y-1">
      <Label htmlFor={`f-${k}`}>{label}</Label>
      <Input id={`f-${k}`} type="number" step={step} value={(value[k] as number | undefined) ?? ""}
        onChange={(e) => set(k, e.target.value === "" ? "" : (Number(e.target.value) as never))} />
    </div>
  );
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {showGroup && (
        <div className="space-y-1">
          <Label htmlFor="f-group">Posição</Label>
          <GroupSelect id="f-group" value={value.group ?? ""} onChange={(v) => set("group", v)} />
        </div>
      )}
      <div className="space-y-1">
        <Label htmlFor="f-comp">Competição</Label>
        <Select id="f-comp" value={value.competition ?? ""} onChange={(e) => set("competition", e.target.value)}>
          <option value="">Todas</option>
          {competitions.map((c) => <option key={c} value={c}>{c}</option>)}
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="f-club">Clube</Label>
        <Input id="f-club" value={value.club ?? ""} onChange={(e) => set("club", e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="f-nat">Nacionalidade</Label>
        <Input id="f-nat" value={value.nationality ?? ""} onChange={(e) => set("nationality", e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="f-foot">Pé preferido</Label>
        <Select id="f-foot" value={value.foot ?? ""} onChange={(e) => set("foot", e.target.value as BaseFilters["foot"])}>
          <option value="">Qualquer</option>
          <option value="right">Direito</option>
          <option value="left">Esquerdo</option>
          <option value="both">Ambos</option>
        </Select>
      </div>
      {num("min_minutes", "Minutos jogados ≥")}
      {num("min_age", "Idade mín.")}
      {num("max_age", "Idade máx.")}
      {num("max_value", "Valor máx. (£)", 100000)}
      {num("max_wage", "Salário máx. (£/sem)", 1000)}
      {num("contract_within_days", "Contrato acaba em ≤ dias", 30)}
      {num("min_potential_gap", "PA − CA ≥")}
    </div>
  );
}

const STATUS_VARIANT: Record<AvailabilityStatus, "default" | "secondary" | "warning" | "destructive" | "outline"> = {
  AVAILABLE: "default", CALCULABLE: "default", CUSTOM: "secondary", PARTIAL: "warning", UNAVAILABLE: "outline", INVALID: "destructive",
};

export function StatusBadge({ status, title }: { status: AvailabilityStatus; title?: string }) {
  return <Badge variant={STATUS_VARIANT[status]} title={title} className="font-normal">{STATUS_LABEL[status]}</Badge>;
}

export function PctCell({ p, compact }: { p: number | null | undefined; compact?: boolean }) {
  if (p === null || p === undefined) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <span className={cn("inline-flex items-center gap-1.5", compact ? "w-20" : "w-28")} title={`Percentil ${Math.round(p)}`}>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full bg-chart-1" style={{ width: `${Math.max(2, p)}%` }} />
      </span>
      <span className="w-6 text-right text-xs tabular-nums">{Math.round(p)}</span>
    </span>
  );
}

export function PlayerLink({ id, name }: { id: number; name: string }) {
  return <Link to={`/jogador/${id}`} className="font-medium hover:underline">{name}</Link>;
}

export function AddToShortlist({ playerIds, source }: { playerIds: number[]; source: string }) {
  const { shortlists, reloadShortlists } = useStats();
  const [msg, setMsg] = useState<string | null>(null);
  const [target, setTarget] = useState("");
  const add = async () => {
    if (!playerIds.length) return;
    let id = Number(target);
    if (!target) {
      const name = window.prompt("Nome da nova shortlist");
      if (!name) return;
      id = (await postJson<{ id: number }>("/api/stats/shortlists", { name })).id;
    }
    const r = await postJson<{ added: number }>(`/api/stats/shortlists/${id}/items`, { player_ids: playerIds, source });
    setMsg(`${r.added} adicionados`);
    await reloadShortlists();
  };
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Select aria-label="Shortlist" className="h-8 w-44" value={target} onChange={(e) => setTarget(e.target.value)}>
        <option value="">Nova shortlist…</option>
        {shortlists.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </Select>
      <Button size="sm" variant="outline" disabled={!playerIds.length} onClick={() => void add()}>
        <ListPlus /> Adicionar {playerIds.length > 1 ? `${playerIds.length} jogadores` : ""}
      </Button>
      {msg && <span className="text-xs text-attr-good">{msg}</span>}
    </span>
  );
}

export function Notes({ notes }: { notes: string[] }) {
  if (!notes.length) return null;
  return (
    <ul className="space-y-0.5 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
      {notes.map((n) => <li key={n}>{n}</li>)}
    </ul>
  );
}

export function Section({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
        {right}
      </div>
      {children}
    </div>
  );
}
