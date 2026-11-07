import { cn } from "@/lib/utils";

// Disposição do campo (ataque em cima). Cada linha é uma faixa do campo.
const ROWS: (string | null)[][] = [
  [null, "ST", null],
  ["AML", "AMC", "AMR"],
  ["ML", "MC", "MR"],
  ["WBL", "DM", "WBR"],
  ["DL", "DC", "DR"],
  [null, "SW", null],
  [null, "GK", null],
];

const LABEL: Record<string, string> = {
  GK: "GR", SW: "LIB", DL: "DE", DC: "DC", DR: "DD", WBL: "AE", WBR: "AD", DM: "MDC",
  ML: "ME", MC: "MC", MR: "MD", AML: "EE", AMC: "MOC", AMR: "ED", ST: "PL",
};

type Props = { ratings: Record<string, number>; natural: string[]; accomplished: string[] };

/** Usa as classificações 1–20 quando a fonte as tem (save); senão as listas natural/competente. */
export function PositionPitch({ ratings, natural, accomplished }: Props) {
  const hasRatings = Object.keys(ratings).length > 0;
  const level = (pos: string): number => {
    if (hasRatings) return ratings[pos] ?? 0;
    if (natural.includes(pos)) return 20;
    if (accomplished.includes(pos)) return 15;
    return 0;
  };
  const tone = (v: number) =>
    v >= 18 ? "bg-attr-good text-white border-attr-good"
    : v >= 15 ? "bg-attr-good/45 border-attr-good/60"
    : v >= 10 ? "bg-attr-mid/30 border-attr-mid/50"
    : v >= 5 ? "bg-card/70 border-pitch-line text-muted-foreground"
    : "border-transparent text-muted-foreground/40";

  return (
    <div>
      <div className="relative mx-auto grid max-w-[260px] gap-1.5 rounded-lg border border-pitch-line bg-pitch p-3">
        {ROWS.map((row, i) => (
          <div key={i} className="grid grid-cols-3 gap-1.5">
            {row.map((pos, j) =>
              pos ? (
                <div
                  key={pos}
                  title={hasRatings ? `${LABEL[pos]}: ${ratings[pos] ?? "—"}/20` : LABEL[pos]}
                  className={cn("rounded-md border py-1 text-center text-[11px] font-semibold leading-tight", tone(level(pos)))}
                >
                  {LABEL[pos]}
                  {hasRatings && <div className="text-[10px] font-normal opacity-80">{ratings[pos] ?? "—"}</div>}
                </div>
              ) : (
                <div key={j} />
              ),
            )}
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap justify-center gap-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-attr-good" /> natural</span>
        <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-attr-good/45" /> competente</span>
        {hasRatings && <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-attr-mid/30" /> razoável</span>}
      </div>
      {!hasRatings && (
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          Esta fonte não tem a classificação 1–20 por posição.
        </p>
      )}
    </div>
  );
}

export const POSITION_LABEL = LABEL;
