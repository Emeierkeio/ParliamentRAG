const API = process.env.FASCICOLI_API_URL || "https://api-production-a731.up.railway.app";
const TTL_MS = 60 * 60 * 1000;

/**
 * The names the verifier recognizes for each group, Misto component and the
 * Government, read from the verifier itself (VOICES in Fascicoli) so the
 * table on /verifica is never a copy that can drift. Kept in memory for an
 * hour.
 */
let cache: { at: number; body: unknown } | null = null;

export const dynamic = "force-dynamic";

export async function GET() {
  if (cache && Date.now() - cache.at < TTL_MS) return Response.json(cache.body);
  const key = process.env.FASCICOLI_API_KEY;
  if (!key) return Response.json({ detail: "verifier not configured" }, { status: 503 });
  try {
    const res = await fetch(`${API}/api/verify/voices`, {
      headers: { "x-api-key": key },
      signal: AbortSignal.timeout(15_000),
    });
    if (!res.ok) return Response.json({ detail: "verifier error" }, { status: 502 });
    const body = await res.json();
    if (!Array.isArray(body?.voices)) return Response.json({ detail: "verifier error" }, { status: 502 });
    cache = { at: Date.now(), body };
    return Response.json(body);
  } catch {
    return Response.json({ detail: "verifier unavailable" }, { status: 504 });
  }
}
