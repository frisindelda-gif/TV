import { CheckCircle2, FileInput, FlaskConical, Loader2, MonitorPlay, ShieldCheck, XCircle } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { getJson, postJson, type ImportOut, type Integrity, type Run } from "@/api";
import { ErrorBox, SyntheticBadge } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { CONNECTOR_LABEL, fieldLabel, fmtDate, fmtDateTime } from "@/lib/format";

// Caminhos lembrados apenas neste browser, por conveniência.
function remembered(key: string): string {
  try {
    return localStorage.getItem(`fm27si.${key}`) ?? "";
  } catch {
    return "";
  }
}
function remember(key: string, v: string) {
  try {
    localStorage.setItem(`fm27si.${key}`, v);
  } catch {
    /* ignorar */
  }
}

const CHECK_LABEL: Record<string, string> = {
  snapshots_match_run_count: "Registos gravados = jogadores importados",
  all_source_players_imported: "Todos os jogadores da fonte foram importados",
  no_duplicate_player_in_run: "Sem jogadores duplicados",
  snapshots_belong_to_run_career: "Todos os registos pertencem à carreira",
  unique_id_unique_in_run: "Unique IDs únicos",
  ca_in_range_1_200: "CA entre 1 e 200",
  pa_in_range_1_200: "PA entre 1 e 200",
  one_attribute_row_per_snapshot: "Atributos gravados para cada jogador",
  attributes_in_range: "Atributos dentro da escala",
  attributes_complete_52: "52 atributos completos",
};

export default function ImportPage() {
  const { career, careers, reload, setCareerId } = useCareer();
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<ImportOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);

  const [savePath, setSavePath] = useState(() => remembered("savePath"));
  const [careerKey, setCareerKey] = useState(() => remembered("careerKey"));
  const [dumpPath, setDumpPath] = useState(() => remembered("dumpPath"));
  const [scannerPath, setScannerPath] = useState(() => remembered("scannerPath"));
  const [runScanner, setRunScanner] = useState(() => remembered("runScanner") === "1");

  const loadRuns = useCallback(() => {
    if (!career) return setRuns([]);
    getJson<Run[]>(`/api/careers/${career.id}/runs`).then((r) => setRuns([...r].reverse())).catch(() => setRuns([]));
  }, [career]);
  useEffect(loadRuns, [loadRuns]);

  const run = async (label: string, fn: () => Promise<ImportOut | ImportOut[]>) => {
    setBusy(label);
    setError(null);
    setResult(null);
    try {
      const out = await fn();
      const list = Array.isArray(out) ? out : [out];
      setResult(list);
      await reload();
      const last = list.at(-1);
      if (last) setCareerId(last.run.career_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const onSave = (e: FormEvent) => {
    e.preventDefault();
    remember("savePath", savePath);
    remember("careerKey", careerKey);
    void run("save", () => postJson<ImportOut>("/api/import/save", { path: savePath.trim().replace(/^"|"$/g, ""), career_key: careerKey.trim() || null }));
  };

  const onLive = (e: FormEvent) => {
    e.preventDefault();
    remember("dumpPath", dumpPath);
    remember("scannerPath", scannerPath);
    remember("runScanner", runScanner ? "1" : "0");
    remember("careerKey", careerKey);
    void run("live", () =>
      postJson<ImportOut>("/api/import/live", {
        dump_path: dumpPath.trim().replace(/^"|"$/g, "") || null,
        run_scanner: runScanner,
        scanner_path: scannerPath.trim().replace(/^"|"$/g, "") || null,
        career_key: careerKey.trim() || null,
      }),
    );
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Dados</h1>
        <p className="text-sm text-muted-foreground">
          Tudo é lido localmente. O save é copiado antes de ser lido e o jogo nunca é alterado.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-1 pt-4">
          <Label htmlFor="career-key">Nome da carreira (recomendado)</Label>
          <Input
            id="career-key"
            value={careerKey}
            onChange={(e) => setCareerKey(e.target.value)}
            placeholder="p.ex. sporting-2026"
            className="max-w-sm"
          />
          <p className="text-xs text-muted-foreground">
            Use sempre o mesmo nome para a mesma carreira, no save e na leitura do jogo. Sem nome, a app tenta adivinhar
            pela combinação treinador + save/clube, o que falha se usar o mesmo nome de treinador em várias carreiras.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-1.5"><FileInput className="size-4" /> Importar save (.fm)</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={onSave} className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="save-path">Caminho do ficheiro</Label>
                <Input
                  id="save-path"
                  required
                  value={savePath}
                  onChange={(e) => setSavePath(e.target.value)}
                  placeholder="C:\Users\…\Football Manager 27\games\carreira.fm"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Inclui estatísticas, classificação por posição e contrato completo. No FM27 os valores ainda estão por
                confirmar pela biblioteca de leitura.
              </p>
              <Button type="submit" disabled={busy !== null} className="w-full">
                {busy === "save" ? <Loader2 className="animate-spin" /> : null} Importar save
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-1.5"><MonitorPlay className="size-4" /> Ler o jogo (memória)</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={onLive} className="space-y-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={runScanner} onChange={(e) => setRunScanner(e.target.checked)} className="size-4 accent-[hsl(var(--primary))]" />
                Fazer nova leitura agora (FM27 aberto)
              </label>
              {runScanner && (
                <div className="space-y-1">
                  <Label htmlFor="scanner">Scanner do FMSuperScout</Label>
                  <Input id="scanner" value={scannerPath} onChange={(e) => setScannerPath(e.target.value)} placeholder="C:\…\FMSuperScout.Scanner.exe" />
                </div>
              )}
              <div className="space-y-1">
                <Label htmlFor="dump">dump.json (opcional)</Label>
                <Input id="dump" value={dumpPath} onChange={(e) => setDumpPath(e.target.value)} placeholder="%LOCALAPPDATA%\FMSuperScout\dump.json" />
              </div>
              <p className="text-xs text-muted-foreground">Rápido e sem gravar o jogo. Não inclui estatísticas.</p>
              <Button type="submit" disabled={busy !== null} className="w-full">
                {busy === "live" ? <Loader2 className="animate-spin" /> : null} Importar leitura
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-1.5"><FlaskConical className="size-4" /> Demonstração</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Cria uma carreira fictícia com 400 jogadores e 3 épocas para experimentar a app sem o jogo. Fica sempre
              marcada como <b>dados sintéticos</b>.
            </p>
            <Button
              variant="outline"
              disabled={busy !== null}
              className="w-full"
              onClick={() => void run("demo", () => postJson<ImportOut[]>("/api/import/demo?players=400&seasons=3"))}
            >
              {busy === "demo" ? <Loader2 className="animate-spin" /> : null} Criar carreira de demonstração
            </Button>
          </CardContent>
        </Card>
      </div>

      {error && <ErrorBox message={error} />}
      {result && <ResultCard results={result} />}

      <Card>
        <CardHeader>
          <CardTitle>Importações {career && <span className="font-normal text-muted-foreground">— {career.label}</span>}</CardTitle>
          {careers && careers.length > 1 && <span className="text-xs text-muted-foreground">mude de carreira no topo</span>}
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Ainda não há importações.</p>
          ) : (
            <div className="space-y-2">
              {runs.map((r) => <RunRow key={r.id} run={r} />)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ResultCard({ results }: { results: ImportOut[] }) {
  return (
    <Card className="border-primary/40">
      <CardContent className="space-y-2 pt-4 text-sm">
        {results.map((r) => (
          <div key={r.run.id}>
            <div className="flex flex-wrap items-center gap-2">
              <CheckCircle2 className="size-4 text-attr-good" />
              {r.duplicate ? (
                <span>Este ficheiro já tinha sido importado (importação #{r.run.id}). Nada foi duplicado.</span>
              ) : (
                <span>
                  Importação #{r.run.id}: <b>{r.run.player_count.toLocaleString("pt-PT")}</b> jogadores ({r.created_players} novos,{" "}
                  {r.updated_players} atualizados) · data no jogo {fmtDate(r.run.game_date)}
                </span>
              )}
              {r.run.synthetic && <SyntheticBadge />}
            </div>
            {r.warnings.length > 0 && (
              <ul className="ml-6 mt-1 list-disc text-xs text-muted-foreground">
                {r.warnings.slice(0, 8).map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            )}
          </div>
        ))}
        <Link to="/jogadores" className="inline-block text-primary hover:underline">Ver jogadores →</Link>
      </CardContent>
    </Card>
  );
}

function RunRow({ run }: { run: Run }) {
  const [report, setReport] = useState<Integrity | null>(null);
  const [open, setOpen] = useState(false);

  const toggle = () => {
    setOpen((o) => !o);
    if (!report) getJson<Integrity>(`/api/runs/${run.id}/integrity`).then(setReport).catch(() => setReport(null));
  };

  return (
    <div className="rounded-md border">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 text-sm">
        <span className="font-medium">#{run.id}</span>
        <Badge variant="secondary">{CONNECTOR_LABEL[run.connector] ?? run.connector}</Badge>
        <span>Jogo: <b>{fmtDate(run.game_date)}</b>{run.season_label && <span className="text-muted-foreground"> ({run.season_label})</span>}</span>
        <span className="tabular-nums">{run.player_count.toLocaleString("pt-PT")} jogadores</span>
        {run.error_count > 0 && <Badge variant="destructive">{run.error_count} com erros</Badge>}
        {run.warning_count > 0 && <Badge variant="warning">{run.warning_count} com avisos</Badge>}
        {run.synthetic && <SyntheticBadge />}
        <span className="text-xs text-muted-foreground">importado {fmtDateTime(run.imported_at)}</span>
        <Button variant="outline" size="sm" className="ml-auto" onClick={toggle}>
          <ShieldCheck /> {open ? "Fechar" : "Integridade"}
        </Button>
      </div>
      {open && (
        <div className="border-t px-3 py-3 text-sm">
          {!report ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className={report.ok ? "mb-2 font-medium text-attr-good" : "mb-2 font-medium text-destructive"}>
                  {report.ok ? "Todas as verificações passaram" : "Há verificações que falharam"}
                </div>
                <ul className="space-y-1">
                  {report.checks.map((c) => (
                    <li key={c.name} className="flex items-start gap-1.5">
                      {c.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-attr-good" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />}
                      <span>{CHECK_LABEL[c.name] ?? c.name}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="space-y-3">
                <Info title="Cobertura (jogadores com o valor)">
                  {Object.entries(report.coverage).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2"><span className="text-muted-foreground">{fieldLabel(k)}</span><span className="tabular-nums">{v === null ? "—" : `${Math.round(v * 100)}%`}</span></div>
                  ))}
                </Info>
                <Info title="Ficheiro">
                  <div className="break-all text-xs text-muted-foreground">{run.source_path ?? "—"}</div>
                  <div className="text-xs text-muted-foreground">{run.tool}</div>
                </Info>
                {run.warnings.length > 0 && (
                  <Info title="Avisos">
                    <ul className="list-disc pl-4 text-xs text-muted-foreground">{run.warnings.slice(0, 10).map((w, i) => <li key={i}>{w}</li>)}</ul>
                  </Info>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Info({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      {children}
    </div>
  );
}
