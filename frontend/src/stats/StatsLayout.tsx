import { NavLink, Outlet } from "react-router-dom";
import { EmptyState } from "@/components/common";
import { useCareer } from "@/lib/career";
import { cn } from "@/lib/utils";

const SECTIONS: [string, string][] = [
  ["/stats", "Overview"],
  ["/stats/rankings", "Position Rankings"],
  ["/stats/percentiles", "Percentile Analysis"],
  ["/stats/filters", "Advanced Filters"],
  ["/stats/identify", "Player Identification"],
  ["/stats/compare", "Player Comparison"],
  ["/stats/market", "Market Opportunities"],
  ["/stats/shortlists", "Shortlists"],
  ["/stats/availability", "Metric Availability"],
  ["/stats/catalog", "Metric Catalog"],
  ["/stats/composites", "Composite Score Builder"],
];

export default function StatsLayout() {
  const { careers, career } = useCareer();
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Statistical Scouting</h1>
        <p className="text-sm text-muted-foreground">
          Métricas de rendimento a partir das estatísticas do jogo. Valores observados, por 90 minutos, percentis e
          indicadores compostos aparecem sempre identificados.
        </p>
      </div>
      <nav className="-mx-1 flex gap-1 overflow-x-auto pb-1" aria-label="Secções do Statistical Scouting">
        {SECTIONS.map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/stats"}
            className={({ isActive }) =>
              cn(
                "shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium",
                isActive ? "border-primary bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      {careers !== null && !career ? (
        <EmptyState title="Ainda não há dados importados">Importe um save em Dados para usar o Statistical Scouting.</EmptyState>
      ) : (
        <Outlet />
      )}
    </div>
  );
}
