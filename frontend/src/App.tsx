import { Database, LayoutDashboard, Moon, Sun, Users } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ErrorBox, SyntheticBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { useCareer } from "@/lib/career";
import { CONNECTOR_LABEL, fmtDate } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import ImportPage from "@/pages/ImportPage";
import OverviewPage from "@/pages/OverviewPage";
import PlayerPage from "@/pages/PlayerPage";
import PlayersPage from "@/pages/PlayersPage";

function NavItem({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
        )
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

export default function App() {
  const { careers, career, latestRun, setCareerId, error } = useCareer();
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5">
          <div className="flex items-center gap-2 font-semibold">
            <span className="grid size-7 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">27</span>
            <span className="hidden md:inline">Scouting Intelligence</span>
          </div>
          <nav className="flex items-center gap-1">
            <NavItem to="/painel" icon={<LayoutDashboard className="size-4" />}>Painel</NavItem>
            <NavItem to="/jogadores" icon={<Users className="size-4" />}>Jogadores</NavItem>
            <NavItem to="/dados" icon={<Database className="size-4" />}>Dados</NavItem>
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-2">
            {careers && careers.length > 0 && (
              <Select
                aria-label="Carreira"
                className="h-8 w-auto max-w-[240px]"
                value={career?.id ?? ""}
                onChange={(e) => setCareerId(Number(e.target.value))}
              >
                {careers.map((c) => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </Select>
            )}
            <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Mudar tema">
              {theme === "dark" ? <Sun /> : <Moon />}
            </Button>
          </div>
        </div>
        {latestRun && (
          <div className="border-t bg-muted/40">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-1 text-xs text-muted-foreground">
              <span>
                Última importação: <b className="text-foreground">{CONNECTOR_LABEL[latestRun.connector]}</b>
              </span>
              <span>Data no jogo: <b className="text-foreground">{fmtDate(latestRun.game_date)}</b></span>
              {latestRun.season_label && <span>Época {latestRun.season_label}</span>}
              <span>{latestRun.player_count.toLocaleString("pt-PT")} jogadores</span>
              {latestRun.synthetic && <SyntheticBadge />}
              {latestRun.game_version_supported === false && (
                <span className="text-warning">Versão do jogo não verificada — dados podem estar errados</span>
              )}
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-7xl px-4 py-5">
        {error && <div className="mb-4"><ErrorBox message={`Não foi possível contactar o backend: ${error}`} /></div>}
        <Routes>
          <Route path="/" element={<Navigate to="/painel" replace />} />
          <Route path="/painel" element={<OverviewPage />} />
          <Route path="/jogadores" element={<PlayersPage />} />
          <Route path="/jogador/:id" element={<PlayerPage />} />
          <Route path="/dados" element={<ImportPage />} />
          <Route path="*" element={<Navigate to="/jogadores" replace />} />
        </Routes>
      </main>
    </div>
  );
}
