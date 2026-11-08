import { ArrowLeft, Info } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getJson, type Category, type Profile } from "@/api";
import {
  AbilityPill,
  AttrValue,
  ErrorBox,
  QualityIcon,
  Stat,
  StatusBadge,
  SyntheticBadge,
} from "@/components/common";
import { EvaluationSection } from "@/components/evaluation/EvaluationSection";
import { PerformanceCard } from "@/components/Performance";
import { StatsProfileSection } from "@/stats/ProfileSection";
import { POSITION_LABEL, PositionPitch } from "@/components/PositionPitch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import {
  COMPETITION_LABEL,
  CONNECTOR_LABEL,
  FOOT_LABEL,
  STATUS_HELP,
  fieldLabel,
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtMoney,
} from "@/lib/format";

const CAT_TITLE: Record<Category, string> = {
  technical: "Técnicos",
  mental: "Mentais",
  physical: "Físicos",
  goalkeeping: "Guarda-redes",
  hidden: "Escondidos",
  personality: "Personalidade",
};

export default function PlayerPage() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const runId = params.get("run");
  const [p, setP] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    getJson<Profile>(`/api/players/${id}${runId ? `?run_id=${runId}` : ""}`, ctrl.signal)
      .then(setP)
      .catch((e: Error) => e.name !== "AbortError" && setError(e.message));
    return () => ctrl.abort();
  }, [id, runId]);

  if (error) return <ErrorBox message={error} />;
  if (!p) return <div className="text-sm text-muted-foreground">A carregar…</div>;

  const isGk = p.positions.natural.includes("GK");
  const mainCats: Category[] = isGk ? ["goalkeeping", "mental", "physical"] : ["technical", "mental", "physical"];
  const latestRunId = p.history.at(-1)?.run_id;
  const viewingOld = p.provenance.run_id !== latestRunId;
  const c = p.contract;
  const cur = p.provenance.currency;
  const st = p.field_status;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" size="sm" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/jogadores"))}>
          <ArrowLeft /> Voltar
        </Button>
        {p.history.length > 1 && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Ver dados de
            <Select
              className="h-8 w-auto"
              value={p.provenance.run_id}
              onChange={(e) => {
                const v = Number(e.target.value);
                setParams(v === latestRunId ? {} : { run: String(v) });
              }}
            >
              {[...p.history].reverse().map((h) => (
                <option key={h.run_id} value={h.run_id}>
                  {fmtDate(h.game_date)} · {CONNECTOR_LABEL[h.connector] ?? h.connector}
                  {h.run_id === latestRunId ? " (mais recente)" : ""}
                </option>
              ))}
            </Select>
          </label>
        )}
      </div>

      {viewingOld && (
        <div className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          Está a ver dados antigos ({fmtDate(p.provenance.game_date)}).
        </div>
      )}

      {/* Cabeçalho */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">{p.name}</h1>
                <QualityIcon quality={p.quality} />
                {p.provenance.synthetic && <SyntheticBadge />}
                {p.growth?.is_new && <Badge variant="secondary">novo nesta importação</Badge>}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                {[
                  p.age !== null ? `${p.age} anos` : null,
                  p.birth_date ? `nasc. ${fmtDate(p.birth_date)}` : p.birth_year ? `nasc. ${p.birth_year}` : null,
                  p.nationalities.length ? p.nationalities.join(" / ") : null,
                  p.height_cm ? `${p.height_cm} cm` : null,
                  p.foot.preferred ? `pé ${FOOT_LABEL[p.foot.preferred]?.toLowerCase() ?? p.foot.preferred}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {p.club.name ? (
                  <Link
                    to={`/jogadores?club=${encodeURIComponent(p.club.name)}`}
                    className="text-sm font-medium text-primary hover:underline"
                  >
                    {p.club.name}
                  </Link>
                ) : (
                  <span className="text-sm text-muted-foreground">Sem clube</span>
                )}
                {p.club.division && <span className="text-sm text-muted-foreground">· {p.club.division}</span>}
                <span className="mx-1 text-muted-foreground">|</span>
                {p.positions.natural.map((x) => <Badge key={x}>{POSITION_LABEL[x] ?? x}</Badge>)}
                {p.positions.accomplished.map((x) => <Badge key={x} variant="secondary">{POSITION_LABEL[x] ?? x}</Badge>)}
              </div>
            </div>
            <div className="flex gap-3">
              <AbilityBox label="CA" value={p.ability.ca} status={st.ca} delta={p.growth?.ca_delta ?? null} />
              <AbilityBox
                label="PA"
                value={p.ability.pa}
                status={st.pa}
                note={p.ability.pa === null && p.ability.pa_range_code !== null ? `código ${p.ability.pa_range_code}` : undefined}
              />
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 border-t pt-4 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Valor" hint={<StatusBadge status={st.market_value} />}>{fmtMoney(p.market_value, cur)}</Stat>
            <Stat label="Salário / semana" hint={<StatusBadge status={st["contract.wage_weekly"]} />}>{fmtMoney(c?.wage_weekly, cur)}</Stat>
            <Stat label="Contrato até">{fmtDate(c?.expires)}</Stat>
            <Stat label="Reputação mundial">{fmtInt(p.reputation.world)}</Stat>
            <Stat label="Reputação atual">{fmtInt(p.reputation.current)}</Stat>
            <Stat label="Unique ID">{p.unique_id ?? "—"}</Stat>
          </div>
        </CardContent>
      </Card>

      <EvaluationSection playerId={p.player_id} runId={viewingOld ? p.provenance.run_id : null} />

      {/* Atributos + posições */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card>
          <CardHeader>
            <CardTitle>Atributos</CardTitle>
            <StatusBadge status={st.attributes} />
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-3">
            {mainCats.map((cat) => <AttributeColumn key={cat} title={CAT_TITLE[cat]} values={p.attributes[cat]} />)}
          </CardContent>
          {isGk && p.attributes.technical && (
            <CardContent className="border-t pt-4">
              <AttributeColumn title="Técnicos" values={p.attributes.technical} columns />
            </CardContent>
          )}
        </Card>
        <Card>
          <CardHeader><CardTitle>Posições</CardTitle></CardHeader>
          <CardContent>
            <PositionPitch ratings={p.positions.ratings} natural={p.positions.natural} accomplished={p.positions.accomplished} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Atributos escondidos</CardTitle>
            <span className="text-xs text-muted-foreground">não visíveis no jogo</span>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-2">
            <AttributeColumn title="Escondidos" values={p.attributes.hidden} />
            <AttributeColumn title="Personalidade" values={p.attributes.personality} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Contrato</CardTitle></CardHeader>
          <CardContent>
            {c ? (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <Dt label="Salário / semana">{fmtMoney(c.wage_weekly, cur)}</Dt>
                <Dt label="Início">{fmtDate(c.start)}</Dt>
                <Dt label="Fim">{fmtDate(c.expires)}</Dt>
                <Dt label="Estatuto">{c.squad_status ? c.squad_status.replaceAll("_", " ").toLowerCase() : "—"}</Dt>
                <Dt label="Situação">
                  <span className="flex flex-wrap gap-1">
                    {c.transfer_listed && <Badge variant="warning">listado</Badge>}
                    {c.loan_listed && <Badge variant="secondary">disponível p/ empréstimo</Badge>}
                    {c.not_for_sale && <Badge variant="secondary">intransferível</Badge>}
                    {c.set_for_release && <Badge variant="destructive">a dispensar</Badge>}
                    {c.transfer_listed === null && c.not_for_sale === null ? "—" : null}
                    {!c.transfer_listed && !c.loan_listed && !c.not_for_sale && !c.set_for_release && c.transfer_listed !== null && "normal"}
                  </span>
                </Dt>
                <Dt label="Empréstimo">
                  {c.on_loan ? `de ${c.loan_parent_club ?? "?"}${c.loan_end ? ` até ${fmtDate(c.loan_end)}` : ""}` : c.on_loan === false ? "não" : "—"}
                </Dt>
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">Sem contrato (ou a fonte não o fornece).</p>
            )}
            {p.traits.length > 0 && (
              <div className="mt-4 border-t pt-3">
                <div className="mb-1.5 text-xs text-muted-foreground">Traços</div>
                <div className="flex flex-wrap gap-1">
                  {p.traits.map((t) => <Badge key={t} variant="outline">{t.replaceAll("_", " ").toLowerCase()}</Badge>)}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <StatsProfileSection playerId={p.player_id} runId={viewingOld ? p.provenance.run_id : null} />

      <PerformanceCard metrics={p.metrics} connector={p.provenance.connector} />

      <EvolutionCard p={p} />

      <Card>
        <CardHeader><CardTitle>Estatísticas da época (totais)</CardTitle></CardHeader>
        <CardContent>
          {p.season_stats.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="py-1.5 pr-2 font-medium">Competição</th>
                    <th className="px-2 font-medium">Clube</th>
                    <th className="px-2 text-right font-medium">Jogos</th>
                    <th className="px-2 text-right font-medium">Min.</th>
                    <th className="px-2 text-right font-medium">Golos</th>
                    <th className="px-2 text-right font-medium">Assist.</th>
                    <th className="px-2 text-right font-medium">xG</th>
                    <th className="px-2 text-right font-medium">xA</th>
                    <th className="px-2 text-right font-medium">Nota</th>
                    <th className="px-2 text-right font-medium">Amarelos</th>
                    <th className="px-2 text-right font-medium">Verm.</th>
                  </tr>
                </thead>
                <tbody>
                  {p.season_stats.map((s, i) => (
                    <tr key={i} className="border-t tabular-nums">
                      <td className="py-1.5 pr-2">{COMPETITION_LABEL[s.competition_kind] ?? s.competition_kind}</td>
                      <td className="px-2">{s.club_name ?? "—"}</td>
                      <td className="px-2 text-right">{(s.starts ?? 0) + (s.sub_appearances ?? 0)}{s.sub_appearances ? ` (${s.sub_appearances})` : ""}</td>
                      <td className="px-2 text-right">{fmtInt(s.minutes)}</td>
                      <td className="px-2 text-right">{s.goals ?? "—"}</td>
                      <td className="px-2 text-right">{s.assists ?? "—"}</td>
                      <td className="px-2 text-right">{s.expected_goals?.toFixed(2) ?? "—"}</td>
                      <td className="px-2 text-right">{s.expected_assists?.toFixed(2) ?? "—"}</td>
                      <td className="px-2 text-right">{s.average_rating?.toFixed(2) ?? "—"}</td>
                      <td className="px-2 text-right">{s.yellow_cards ?? "—"}</td>
                      <td className="px-2 text-right">{s.red_cards ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {p.provenance.connector === "live_memory"
                ? "A leitura da memória não inclui estatísticas. Importe o save (.fm) para as ver."
                : "Sem jogos registados nesta época."}
            </p>
          )}
        </CardContent>
      </Card>

      <ProvenanceCard p={p} />
    </div>
  );
}

function AbilityBox({ label, value, status, note, delta }: { label: string; value: number | null; status?: Profile["field_status"][string]; note?: string; delta?: number | null }) {
  return (
    <div className="flex min-w-[88px] flex-col items-center rounded-lg border bg-muted/40 px-3 py-2">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <AbilityPill value={value} className="mt-1 text-2xl" />
      {delta !== undefined && delta !== null && delta !== 0 && (
        <div
          className={delta > 0 ? "text-xs font-semibold text-attr-good" : "text-xs font-semibold text-attr-low"}
          title="Variação desde a importação anterior"
        >
          {delta > 0 ? `▲ +${delta}` : `▼ ${delta}`}
        </div>
      )}
      <div className="mt-1">{note ? <span className="text-[11px] text-muted-foreground">{note}</span> : <StatusBadge status={status} />}</div>
    </div>
  );
}

function AttributeColumn({ title, values, columns }: { title: string; values?: Record<string, number>; columns?: boolean }) {
  const { attrLabel } = useCareer();
  // Ordem alfabética pelo nome em português, como no ecrã do FM.
  const entries = Object.entries(values ?? {}).sort(([a], [b]) => attrLabel(a).localeCompare(attrLabel(b), "pt"));
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Não disponível nesta fonte.</p>
      ) : (
        <ul className={columns ? "grid gap-x-6 sm:grid-cols-3" : ""}>
          {entries.map(([k, v]) => (
            <li key={k} className="flex items-center justify-between border-b border-dashed py-1 text-sm last:border-0">
              <span>{attrLabel(k)}</span>
              <AttrValue value={v} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EvolutionCard({ p }: { p: Profile }) {
  const data = p.history.map((h) => ({ ...h, label: fmtDate(h.game_date ?? h.read_at) }));
  const hasValue = data.some((d) => d.market_value !== null);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evolução</CardTitle>
        <span className="text-xs text-muted-foreground">
          {p.history.length} {p.history.length === 1 ? "importação" : "importações"}
        </span>
      </CardHeader>
      <CardContent>
        {p.history.length < 2 ? (
          <p className="text-sm text-muted-foreground">
            O histórico aparece a partir da segunda importação desta carreira (cada importação guarda uma fotografia do jogador).
          </p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-1 text-xs text-muted-foreground">CA e PA</div>
              <div className="h-56">
                <ResponsiveContainer>
                  <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                    <YAxis domain={[0, 200]} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                    <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line isAnimationActive={false} dataKey="ca" name="CA" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3 }} />
                    <Line isAnimationActive={false} dataKey="pa" name="PA" stroke="hsl(var(--attr-elite))" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs text-muted-foreground">Valor</div>
              {hasValue ? (
                <div className="h-56">
                  <ResponsiveContainer>
                    <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                      <YAxis tickFormatter={(v: number) => fmtMoney(v, p.provenance.currency)} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                      <Tooltip
                        formatter={(v) => fmtMoney(Number(v), p.provenance.currency)}
                        contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
                      />
                      <Line isAnimationActive={false} dataKey="market_value" name="Valor" stroke="hsl(var(--attr-good))" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">O jogo não guarda valor para este jogador.</p>
              )}
            </div>
          </div>
        )}
        {p.history.length > 1 && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs tabular-nums">
              <thead className="text-left text-muted-foreground">
                <tr><th className="py-1 font-medium">Data no jogo</th><th className="font-medium">Fonte</th><th className="font-medium">Clube</th><th className="text-right font-medium">CA</th><th className="text-right font-medium">PA</th><th className="text-right font-medium">Valor</th></tr>
              </thead>
              <tbody>
                {[...p.history].reverse().map((h, i, arr) => {
                  const prev = arr[i + 1];
                  const delta = prev && h.ca !== null && prev.ca !== null ? h.ca - prev.ca : null;
                  return (
                    <tr key={h.run_id} className="border-t">
                      <td className="py-1">{fmtDate(h.game_date)}</td>
                      <td>{CONNECTOR_LABEL[h.connector] ?? h.connector}</td>
                      <td>{h.club ?? "—"}</td>
                      <td className="text-right">
                        {h.ca ?? "—"}
                        {delta !== null && delta !== 0 && (
                          <span className={delta > 0 ? "ml-1 text-attr-good" : "ml-1 text-attr-low"}>{delta > 0 ? `+${delta}` : delta}</span>
                        )}
                      </td>
                      <td className="text-right">{h.pa ?? "—"}</td>
                      <td className="text-right">{fmtMoney(h.market_value, p.provenance.currency)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ProvenanceCard({ p }: { p: Profile }) {
  const pv = p.provenance;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5"><Info className="size-4" /> Origem e fiabilidade dos dados</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-3">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
          <dt className="text-muted-foreground">Fonte</dt><dd>{CONNECTOR_LABEL[pv.connector] ?? pv.connector}</dd>
          <dt className="text-muted-foreground">Ferramenta</dt><dd>{pv.tool}</dd>
          <dt className="text-muted-foreground">Data no jogo</dt><dd>{fmtDate(pv.game_date)} <StatusBadge status={pv.game_date_status} /></dd>
          <dt className="text-muted-foreground">Lido em</dt><dd>{fmtDateTime(pv.read_at)}</dd>
          <dt className="text-muted-foreground">Importado em</dt><dd>{fmtDateTime(pv.imported_at)}</dd>
          <dt className="text-muted-foreground">Versão do jogo</dt><dd>{pv.game_version ?? "—"}</dd>
          <dt className="text-muted-foreground">Moeda</dt><dd>{pv.currency === "save_base_unit" ? "unidade interna do save" : pv.currency ?? "—"}</dd>
          <dt className="text-muted-foreground">Ficheiro</dt>
          <dd className="break-all text-xs" title={pv.source_sha256 ?? undefined}>{pv.source_path ?? "—"}</dd>
        </dl>

        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Estado de cada campo</div>
          <ul className="space-y-1 text-sm">
            {Object.entries(p.field_status)
              .sort(([a], [b]) => fieldLabel(a).localeCompare(fieldLabel(b), "pt"))
              .map(([k, v]) => (
              <li key={k} className="flex items-center justify-between gap-2">
                <span className="truncate text-muted-foreground">{fieldLabel(k)}</span>
                <span title={STATUS_HELP[v]}><StatusBadge status={v} /></span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-4">
          <Section title="Problemas de leitura">
            {p.issues.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhum.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {p.issues.map((i, n) => (
                  <li key={n} className={i.severity === "error" ? "text-destructive" : "text-warning"}>
                    <b>{i.field}</b>: {i.message}
                    {i.value !== null && i.value !== undefined && !Array.isArray(i.value) && <> ({String(i.value)})</>}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Não disponível nesta fonte">
            <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
              {p.unavailable_fields.map((f) => <li key={f}>{f}</li>)}
            </ul>
          </Section>
        </div>
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      {children}
    </div>
  );
}

function Dt({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}
