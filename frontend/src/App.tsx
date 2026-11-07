import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getJson, type HistoryPoint, type PlayerPage } from "@/api";
import { Card } from "@/components/ui/card";

// Página de verificação da PoC: confirma que frontend ↔ API ↔ SQLite funcionam.
// Não é a interface final.
export default function App() {
  const [page, setPage] = useState<PlayerPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ name: string; history: HistoryPoint[] } | null>(null);

  useEffect(() => {
    getJson<PlayerPage>("/api/players?limit=25").then(setPage).catch((e: Error) => setError(e.message));
  }, []);

  const open = (id: number) =>
    getJson<{ name: string; history: HistoryPoint[] }>(`/api/players/${id}`).then(setSelected);

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-4">
      <h1 className="text-xl font-semibold">FM27 Scouting Intelligence — verificação da PoC</h1>
      {error && <Card className="p-4 text-sm">Sem dados: {error}. Importe uma carreira primeiro.</Card>}
      {page && (
        <Card className="overflow-x-auto p-0">
          <div className="p-3 text-sm text-muted-foreground">Importação #{page.run_id} · {page.total} jogadores</div>
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr><th className="p-2">Nome</th><th>Idade</th><th>CA</th><th>PA</th><th>Clube</th><th>Pos.</th></tr>
            </thead>
            <tbody>
              {page.items.map((p) => (
                <tr key={p.player_id} className="cursor-pointer border-t hover:bg-muted" onClick={() => open(p.player_id)}>
                  <td className="p-2">{p.name}</td><td>{p.age}</td><td>{p.ca}</td><td>{p.pa}</td>
                  <td>{p.club}</td><td>{p.positions.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {selected && (
        <Card className="p-4">
          <div className="mb-2 font-medium">{selected.name} — evolução de CA/PA</div>
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={selected.history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="game_date" />
                <YAxis domain={[0, 200]} />
                <Tooltip />
                <Line dataKey="ca" name="CA" stroke="hsl(var(--primary))" />
                <Line dataKey="pa" name="PA" stroke="hsl(var(--muted-foreground))" strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </main>
  );
}
