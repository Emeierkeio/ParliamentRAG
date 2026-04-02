import { NextRequest } from "next/server";

/**
 * API Route for the RAG chat
 *
 * Proxy to the FastAPI Python backend that handles:
 * 1. Authority calculation and chunk retrieval
 * 2. Response generation with GPT-4o
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  const { query, task_id } = await request.json();

  if (!query || typeof query !== "string") {
    return new Response(
      JSON.stringify({ error: "Query is required" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  try {
    // Proxy to the FastAPI backend
    const backendResponse = await fetch(`${BACKEND_URL}/api/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify({ query, task_id }),
    });

    if (!backendResponse.ok) {
      throw new Error(`Backend error: ${backendResponse.status}`);
    }

    // Direct stream from the backend
    const reader = backendResponse.body?.getReader();
    if (!reader) {
      throw new Error("No response body");
    }

    const stream = new ReadableStream({
      async start(controller) {
        const decoder = new TextDecoder();
        const encoder = new TextEncoder();
        let buffer = ""; // Buffer for partial messages

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // Decode and append to buffer
            buffer += decoder.decode(value, { stream: true });

            // Process only complete messages (terminated with \n\n)
            const messages = buffer.split("\n\n");

            // Last element may be incomplete — keep it in the buffer
            buffer = messages.pop() || "";

            for (const message of messages) {
              const lines = message.split("\n");
              for (const line of lines) {
                if (line.startsWith("data:")) {
                  const data = line.substring(5).trim();
                  if (data) {
                    // Pass the JSON directly — it already contains the type field
                    controller.enqueue(encoder.encode(`data: ${data}\n\n`));
                  }
                }
              }
            }
          }

          // Process any remaining data in the buffer
          if (buffer.trim()) {
            const lines = buffer.split("\n");
            for (const line of lines) {
              if (line.startsWith("data:")) {
                const data = line.substring(5).trim();
                if (data) {
                  controller.enqueue(encoder.encode(`data: ${data}\n\n`));
                }
              }
            }
          }
        } catch (error) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "error", message: "Stream error" })}\n\n`));
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });

  } catch (error) {
    console.error("Backend connection error:", error);

    // Fallback: use mock data when backend is unavailable
    return fallbackMockResponse(query);
  }
}

/**
 * Fallback with mock data when the backend is unavailable
 */
function fallbackMockResponse(query: string) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const sendEvent = (type: string, data: Record<string, unknown>) => {
        const event = `data: ${JSON.stringify({ type, ...data })}\n\n`;
        controller.enqueue(encoder.encode(event));
      };

      try {
        // Notify that we are using the fallback
        sendEvent("warning", { message: "Backend non disponibile. Usando dati di esempio." });

        // Simulate the 6 steps of the RAG pipeline
        const steps = [
          { delay: 300, step: 1 },
          { delay: 400, step: 2 },
          { delay: 500, step: 3 },
          { delay: 400, step: 4 },
          { delay: 300, step: 5 },
          { delay: 200, step: 6 },
        ];

        for (const { delay, step } of steps) {
          await new Promise((resolve) => setTimeout(resolve, delay));
          sendEvent("progress", { step });
        }

        // Simulate streaming the response
        const mockContent = `## Risposta di esempio

Il backend ParliamentRAG non è attualmente disponibile.

Per avviare il backend:
\`\`\`bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
\`\`\`

Una volta avviato, potrai:
- Fare domande puntuali (es. "Qual è l'ultima interrogazione sul superbonus?")
- Fare domande generiche (es. "Qual è il posizionamento dei gruppi parlamentari sull'immigrazione?")

Il sistema analizzerà i dibattiti parlamentari della XIX legislatura.`;

        const chunks = mockContent.split(" ");
        for (const chunk of chunks) {
          await new Promise((resolve) => setTimeout(resolve, 30));
          sendEvent("chunk", { content: chunk + " " });
        }

        // Complete
        sendEvent("complete", { messageId: `mock_${Date.now()}` });

      } catch (error) {
        sendEvent("error", { message: "Error during processing" });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
