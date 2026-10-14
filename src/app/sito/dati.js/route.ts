/*
 * window.DATI per le pagine: le citazioni verificate del tema d'esempio
 * (src/sito/dati-base.json) più i numeri del grafo letti dal backend, gli
 * stessi di Fascicoli. Si rigenera al massimo ogni 10 minuti; se il backend
 * non risponde restano i numeri dell'ultima fotografia notturna
 * (src/data/site-data.json, scripts/snapshot-data.mjs).
 */
import base from "@/sito/dati-base.json";
import fotografia from "@/data/site-data.json";
import { SOLO_BASE } from "@/sito/solo-base";

export const revalidate = 600;

const BACKEND = (process.env.PARLIAMENTRAG_API || "https://thesis-parliamentrag-production.up.railway.app").replace(/\/$/, "");

type Stats = Record<string, unknown>;

async function statsVive(): Promise<Stats | null> {
  try {
    const r = await fetch(`${BACKEND}/api/data/stats`, {
      headers: { Accept: "application/json", "User-Agent": "parliamentrag-sito" },
      next: { revalidate },
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) return null;
    return (await r.json()) as Stats;
  } catch {
    return null;
  }
}

function camereComplete(v: unknown): boolean {
  const c = v as Record<string, Record<string, unknown>> | null;
  return ["camera", "senato"].every((ch) => typeof c?.[ch]?.speeches === "number");
}

export async function GET() {
  const stats: Stats = { ...base.stats };
  // Prima la fotografia notturna, poi i valori vivi: vince il più recente disponibile.
  // `triples` viene dall'export RDF: il backend lo restituisce vuoto e resta quello salvato.
  // `by_chamber` (Camera e Senato separati) passa solo intero: una fonte che non
  // l'ha lascia quello precedente, mai mezza divisione.
  for (const fonte of [fotografia as Stats, await statsVive()]) {
    if (!fonte) continue;
    for (const k of Object.keys(base.stats)) {
      if (k === "fonte" || SOLO_BASE.includes(k) || fonte[k] === null || fonte[k] === undefined) continue;
      if (k === "by_chamber" && !camereComplete(fonte[k])) continue;
      stats[k] = fonte[k];
    }
  }
  const dati = { ...base, stats };
  return new Response(`window.DATI=${JSON.stringify(dati)};`, {
    headers: { "Content-Type": "text/javascript; charset=utf-8" },
  });
}
