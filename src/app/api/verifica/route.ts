import { clientIp, overLimit } from "@/lib/server/limits";

const API = process.env.FASCICOLI_API_URL || "https://api-production-a731.up.railway.app";
const MAX_CHARS = 20000;

/**
 * Forwards an answer to the verifier on the Fascicoli backend. The text is
 * neither stored nor logged here: it goes to the verifier and the report
 * comes back.
 */
export async function POST(request: Request) {
  const key = process.env.FASCICOLI_API_KEY;
  if (!key) return Response.json({ detail: "verifier not configured" }, { status: 503 });

  const body = await request.json().catch(() => null);
  const answer = typeof body?.answer === "string" ? body.answer : "";
  const topic = typeof body?.topic === "string" ? body.topic.trim().slice(0, 500) : "";
  if (!answer.trim() || answer.length > MAX_CHARS) {
    return Response.json({ detail: "invalid request" }, { status: 400 });
  }
  // Each check embeds a topic and searches the whole legislature
  if (overLimit(`verifica:${clientIp(request)}`, 20, 3600)) {
    return Response.json({ detail: "too many requests" }, { status: 429 });
  }

  try {
    const res = await fetch(`${API}/api/verify`, {
      method: "POST",
      headers: { "x-api-key": key, "content-type": "application/json", "x-forwarded-for": clientIp(request) },
      body: JSON.stringify({ answer, topic: topic || null }),
      signal: AbortSignal.timeout(90_000),
    });
    if (!res.ok) return Response.json({ detail: "verifier error" }, { status: 502 });
    return Response.json(await res.json());
  } catch {
    return Response.json({ detail: "verifier unavailable" }, { status: 504 });
  }
}
