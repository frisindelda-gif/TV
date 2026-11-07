import type { Confidence } from "@/api";
import { Badge } from "@/components/ui/badge";
import { CONFIDENCE_HELP, CONFIDENCE_LABEL, scoreTone } from "@/lib/evaluation";
import { cn } from "@/lib/utils";

export function ScoreValue({ v, className }: { v: number | null | undefined; className?: string }) {
  return (
    <span className={cn("font-semibold tabular-nums", scoreTone(v), className)}>
      {v === null || v === undefined ? "—" : Math.round(v)}
    </span>
  );
}

/** Barra 0–100 com marcador opcional da média da posição. */
export function ScoreBar({ v, mean, className }: { v: number | null | undefined; mean?: number | null; className?: string }) {
  return (
    <span className={cn("relative block h-1.5 w-full overflow-hidden rounded-full bg-muted", className)} aria-hidden>
      {v !== null && v !== undefined && (
        <span className="absolute inset-y-0 left-0 rounded-full bg-chart-1" style={{ width: `${Math.max(1, v)}%` }} />
      )}
      {mean !== null && mean !== undefined && (
        <span className="absolute inset-y-[-2px] w-0.5 bg-foreground/70" style={{ left: `calc(${mean}% - 1px)` }} />
      )}
    </span>
  );
}

export function ConfidenceBadge({ c, coverage }: { c: Confidence; coverage?: number }) {
  const variant = c === "high" ? "default" : c === "medium" ? "secondary" : "warning";
  const cov = coverage !== undefined && coverage < 1 ? ` · ${Math.round(coverage * 100)}% dos dados` : "";
  return (
    <Badge variant={variant} className="font-normal" title={CONFIDENCE_HELP[c]}>
      confiança {CONFIDENCE_LABEL[c]}
      {cov}
    </Badge>
  );
}
