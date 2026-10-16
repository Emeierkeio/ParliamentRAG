import { clientIp, overLimit } from "@/lib/server/limits";

const API = process.env.FASCICOLI_API_URL || "https://api-production-a731.up.railway.app";
const MAX_CHARS = 20000;
const MAX_V1_CHARS = 200000;

/**
 * Forwards an answer to the verifier on the Fascicoli backend. The text is
 * neither stored nor logged here: it goes to the verifier and the report
 * comes back.
 *
 * Two shapes: { answer, topic } is free text, checked on the three
 * guarantees; { v1 } is an answer in the verifiable format v1
 * (schema/verifiable-answer.v1.json), whose quotes are checked with the
 * public library in verifica/.
 */
export async function POST(request: Request) {
  const key = process.env.FASCICOLI_API_KEY;
  if (!key) return Response.json({ detail: "verifier not configured" }, { status: 503 });

  const body = await request.json().catch(() => null);
  if (body && typeof body.v1 === "object" && body.v1 !== null) return verificaV1(request, key, body.v1);

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

async function verificaV1(request: Request, key: string, answer: object) {
  if (JSON.stringify(answer).length > MAX_V1_CHARS) {
    return Response.json({ detail: "answer too large" }, { status: 413 });
  }
  // No embeddings here: a lookup per quote, so a looser limit
  if (overLimit(`verifica-v1:${clientIp(request)}`, 60, 3600)) {
    return Response.json({ detail: "too many requests" }, { status: 429 });
  }
  try {
    const res = await fetch(`${API}/api/verify/v1`, {
      method: "POST",
      headers: { "x-api-key": key, "content-type": "application/json", "x-forwarded-for": clientIp(request) },
      body: JSON.stringify(answer),
      signal: AbortSignal.timeout(60_000),
    });
    if (res.status === 422) {
      const j = await res.json().catch(() => null);
      return Response.json({ errors: j?.detail?.errors ?? [] }, { status: 422 });
    }
    if (res.status === 413) return Response.json({ detail: "answer too large" }, { status: 413 });
    if (!res.ok) return Response.json({ detail: "verifier error" }, { status: 502 });
    return Response.json(await res.json());
  } catch {
    return Response.json({ detail: "verifier unavailable" }, { status: 504 });
  }
}
