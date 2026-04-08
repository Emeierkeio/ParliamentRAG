"use client";

import { useState, useCallback, useRef } from "react";
import type { TranscriptMessage, TranscriptCitation } from "@/types/transcript";

function getLocale(): string {
  if (typeof document === "undefined") return "it";
  return (
    document.cookie.split("; ").find((c) => c.startsWith("NEXT_LOCALE="))?.split("=")[1] || "it"
  );
}

let msgIdCounter = 0;

export function useTranscriptChat(debateId: string) {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      const userMsg: TranscriptMessage = {
        id: `msg-${++msgIdCounter}`,
        role: "user",
        content: content.trim(),
      };

      // Build history from existing messages (for multi-turn)
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      const assistantId = `msg-${++msgIdCounter}`;
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", citations: [] },
      ]);

      try {
        abortRef.current = new AbortController();
        const response = await fetch(
          `/api/transcript/${encodeURIComponent(debateId)}/chat`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Accept-Language": getLocale(),
            },
            body: JSON.stringify({
              query: content.trim(),
              history,
            }),
            signal: abortRef.current.signal,
          }
        );

        if (!response.ok || !response.body) {
          throw new Error(`Chat failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            try {
              const event = JSON.parse(jsonStr);

              if (event.type === "citations") {
                const cits: TranscriptCitation[] = (event.citations || []).map(
                  (c: Record<string, unknown>) => ({
                    index: c.index as number,
                    speech_id: c.speech_id as string,
                    speaker_name: (c.speaker_name as string) || "",
                    party: (c.party as string) || null,
                    chunk_text: (c.chunk_text as string) || "",
                  })
                );
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, citations: cits } : m
                  )
                );
              }

              if (event.type === "chunk" && event.content) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + event.content }
                      : m
                  )
                );
              }

              if (event.type === "error") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: event.message || "Error" }
                      : m
                  )
                );
              }
            } catch {
              // skip malformed JSON
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: "Something went wrong. Please try again." }
                : m
            )
          );
        }
      } finally {
        setIsLoading(false);
        abortRef.current = null;
      }
    },
    [debateId, messages, isLoading]
  );

  const stopGenerating = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, isLoading, sendMessage, stopGenerating, clearMessages };
}
