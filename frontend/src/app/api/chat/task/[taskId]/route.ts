import { NextRequest } from "next/server";

/**
 * Polling endpoint for recovering task results after SSE disconnection.
 *
 * Proxies to the FastAPI backend GET /api/chat/task/{taskId}.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;

  try {
    const backendResponse = await fetch(
      `${BACKEND_URL}/api/chat/task/${taskId}`,
      { headers: { "Accept": "application/json" } }
    );

    if (!backendResponse.ok) {
      return new Response(
        JSON.stringify({ error: "Task not found" }),
        { status: backendResponse.status, headers: { "Content-Type": "application/json" } }
      );
    }

    const data = await backendResponse.json();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Task polling error:", error);
    return new Response(
      JSON.stringify({ error: "Backend unavailable" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}
