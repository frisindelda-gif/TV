import { AlertTriangle, CircleCheck, CircleX, FlaskConical } from "lucide-react";
import type { ReactNode } from "react";
import type { FieldStatus, Quality } from "@/api";
import { Badge } from "@/components/ui/badge";
import { STATUS_HELP, STATUS_LABEL, abilityTone, attrTone } from "@/lib/format";
import { cn } from "@/lib/utils";

export function StatusBadge({ status }: { status: FieldStatus | undefined }) {
  if (!status) return null;
  const variant = status === "verified" ? "default" : status === "estimate" ? "warning" : "secondary";
  return (
    <Badge variant={variant} title={STATUS_HELP[status]} className="font-normal">
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export function QualityIcon({ quality }: { quality: Quality }) {
  if (quality === "ok") return <CircleCheck className="size-4 text-attr-good" aria-label="Leitura sem problemas" />;
  if (quality === "warning")
    return <AlertTriangle className="size-4 text-warning" aria-label="Leitura com avisos" />;
  return <CircleX className="size-4 text-destructive" aria-label="Leitura com erros" />;
}

export function SyntheticBadge() {
  return (
    <Badge variant="warning" title="Dados de teste gerados pela app — não vêm do jogo">
      <FlaskConical className="size-3" /> dados sintéticos
    </Badge>
  );
}

export function AbilityPill({ value, className }: { value: number | null; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex min-w-9 justify-center rounded-md px-1.5 py-0.5 text-sm font-semibold tabular-nums",
        abilityTone(value),
        className,
      )}
    >
      {value ?? "—"}
    </span>
  );
}

export function AttrValue({ value }: { value: number | undefined }) {
  if (value === undefined) return <span className="text-muted-foreground">—</span>;
  return <span className={cn("font-semibold tabular-nums", attrTone(value))}>{value}</span>;
}

export function Stat({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-lg font-semibold tabular-nums">{children}</div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed p-8 text-center">
      <div className="font-medium">{title}</div>
      {children && <div className="mt-2 text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{message}</div>
  );
}
