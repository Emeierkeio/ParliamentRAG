import { NextRequest } from "next/server";

/**
 * Polling and cancellation endpoint for background query tasks.
 *
 * Proxies to the FastAPI backend GET/DELETE /api/chat/task/{taskId}.
 * The DELETE handler must live here: this route file shadows the catch-all
 * proxy for every HTTP method on this path, so without it the frontend
 * cancel request would get a 405 from Next instead of reaching the backend.
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

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;

  try {
    const backendResponse = await fetch(
      `${BACKEND_URL}/api/chat/task/${taskId}`,
      { method: "DELETE", headers: { "Accept": "application/json" } }
    );

    const data = await backendResponse.text();
    return new Response(data, {
      status: backendResponse.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Task cancel error:", error);
    return new Response(
      JSON.stringify({ error: "Backend unavailable" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}
