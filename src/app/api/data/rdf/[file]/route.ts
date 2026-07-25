import { NextRequest, NextResponse } from "next/server";

/**
 * Streaming proxy for RDF dump downloads.
 * The catch-all /api proxy buffers the whole body as text, which cannot work
 * for multi-GB dumps: this route passes the backend stream through untouched.
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ file: string }> }
) {
  const { file } = await context.params;
  const response = await fetch(
    `${BACKEND_URL}/api/data/rdf/${encodeURIComponent(file)}`
  );
  if (!response.ok || !response.body) {
    return NextResponse.json(
      { error: "File not available" },
      { status: response.status || 404 }
    );
  }
  const headers: Record<string, string> = {
    "Content-Type":
      response.headers.get("Content-Type") ?? "application/octet-stream",
    "Content-Disposition":
      response.headers.get("Content-Disposition") ??
      `attachment; filename="${file}"`,
  };
  const length = response.headers.get("Content-Length");
  if (length) headers["Content-Length"] = length;
  return new NextResponse(response.body, { status: 200, headers });
}
