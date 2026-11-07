// Cliente mínimo para o backend local. Tipos espelham fm27si/api.py.
export type PlayerRow = {
  player_id: number;
  unique_id: number | null;
  name: string;
  age: number | null;
  ca: number | null;
  pa: number | null;
  club: string | null;
  positions: string[];
  market_value: number | null;
  quality: "ok" | "warning" | "error";
};

export type PlayerPage = { run_id: number; total: number; items: PlayerRow[] };

export type HistoryPoint = { run_id: number; game_date: string | null; ca: number | null; pa: number | null };

export async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
