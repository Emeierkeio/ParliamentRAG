"use client";

import { useState, useCallback, useRef } from "react";
import type {
  Message,
  Citation,
  Expert,
  BalanceMetrics,
  ProcessingProgress,
  StepResult,
} from "@/types";
import { config } from "@/config";

interface UseChatOptions {
  onError?: (error: Error) => void;
}

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const abortControllerRef = useRef<AbortController | null>(null);

  // Generate unique ID
  const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

  // Add user message
  const addUserMessage = useCallback((content: string): Message => {
    const newMessage: Message = {
      id: generateId(),
      role: "user",
      content,
      timestamp: new Date(),
      status: "complete",
    };
    
    setMessages((prev) => {
       if (prev.some(m => m.id === newMessage.id)) {
         console.warn("[Pipeline] Duplicate user message skipped:", newMessage.id);
         return prev;
       }
       return [...prev, newMessage];
    });
    return newMessage;
  }, []);

  // Add assistant message
  const addAssistantMessage = useCallback((
    content: string,
    metadata?: {
      citations?: Citation[];
      experts?: Expert[];
      balanceMetrics?: BalanceMetrics;
    }
  ): Message => {
    const newMessage: Message = {
      id: generateId(),
      role: "assistant",
      content,
      timestamp: new Date(),
      status: "complete",
      ...metadata,
    };
    
    setMessages((prev) => {
      if (prev.some(m => m.id === newMessage.id)) {
        console.warn("[Pipeline] Duplicate assistant message skipped:", newMessage.id);
        return prev;
      }
      return [...prev, newMessage];
    });
    return newMessage;
  }, []);

  // Update the last assistant message
  const updateLastAssistantMessage = useCallback((
    updates: Partial<Message>
  ) => {
    setMessages((prev) => {
      const lastIndex = prev.findLastIndex((m) => m.role === "assistant");
      if (lastIndex === -1) return prev;

      const updated = [...prev];
      updated[lastIndex] = { ...updated[lastIndex], ...updates };
      return updated;
    });
  }, []);

  // Send message with streaming support
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    // Abort any previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setStreamingContent("");
    setProgress({
      currentStep: 1,
      totalSteps: config.ui.progressSteps.length,
      stepLabel: config.ui.progressSteps[0].label,
      stepDescription: config.ui.progressSteps[0].description,
      isComplete: false,
      stepResults: [],
    });

    // Add user message
    addUserMessage(content);

    // Add placeholder for assistant message
    const assistantMessage: Message = {
      id: generateId(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
      status: "streaming",
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const response = await fetch(`${config.api.baseUrl}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: content }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let accumulatedContent = "";
      let citations: Citation[] = [];
      let experts: Expert[] = [];
      let balanceMetrics: BalanceMetrics | undefined;
      let compassData: any = null;
      let baselineAnswer = "";
      let abAssignment: Record<string, string> | null = null;
      let buffer = ""; // Buffer per messaggi SSE parziali

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // Flush TextDecoder remaining bytes + process any buffered data
          buffer += decoder.decode();
          if (buffer.trim()) {
            console.warn(`[Pipeline:Buffer] Stream ended with ${buffer.length} bytes in buffer — flushing`);
            const remainingLines = buffer.split("\n").filter((l: string) => l.startsWith("data: "));
            for (const line of remainingLines) {
              try {
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;
                const data = JSON.parse(jsonStr);
                console.log(`[Pipeline:Buffer] Recovered event: "${data.type}"`, data.type === "complete" ? {
                  baseline: typeof data.baseline_answer === "string" ? `${data.baseline_answer.length} chars` : "missing",
                  ab: data.ab_assignment,
                  error: data.baseline_error || "none",
                } : "");
                if (data.type === "complete") {
                  baselineAnswer = data.baseline_answer || "";
                  abAssignment = data.ab_assignment || null;
                  setProgress((prev) => prev ? { ...prev, isComplete: true } : null);
                  updateLastAssistantMessage({
                    status: "complete",
                    content: accumulatedContent,
                    citations,
                    experts,
                    balanceMetrics,
                    baselineAnswer: baselineAnswer || undefined,
                    abAssignment: abAssignment || undefined,
                  });
                }
              } catch (e) {
                console.error(`[Pipeline:Buffer] Failed to parse buffered data:`, e, `raw: "${line.substring(0, 200)}"`);
              }
            }
          }
          break;
        }

        // Aggiungi al buffer e processa solo messaggi completi
        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split("\n\n");
        buffer = messages.pop() || ""; // Mantieni l'ultimo (potenzialmente incompleto)

        const lines = messages
          .flatMap((msg) => msg.split("\n"))
          .filter((line) => line.startsWith("data: "));

        for (const line of lines) {
          try {
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue;

            const data = JSON.parse(jsonStr);

            switch (data.type) {
              case "progress":
                const stepIndex = data.step - 1;
                const step = config.ui.progressSteps[stepIndex];
                console.log(`[Pipeline] Step ${data.step}/${data.total}: ${step?.label || data.message}`);
                setProgress((prev) => ({
                  currentStep: data.step,
                  totalSteps: data.total || config.ui.progressSteps.length,
                  stepLabel: step?.label || data.message || "",
                  stepDescription: step?.description || "",
                  isComplete: false,
                  stepResults: prev?.stepResults || [],
                }));
                break;

              case "commissioni":
                const commList = data.commissioni || [];
                console.log(`[Pipeline] Step 2 result: ${commList.length} commissioni`, commList.map((c: any) => c.name || c));
                setProgress((prev) => prev ? {
                  ...prev,
                  stepResults: [...prev.stepResults, {
                    step: 2,
                    label: "Commissioni",
                    result: `${commList.length} commissioni pertinenti`,
                    details: { commissioni: commList }
                  }]
                } : null);
                break;

              case "experts":
                const expertsPayload = data.data || data.experts;
                if (Array.isArray(expertsPayload)) {
                  experts = expertsPayload;
                  updateLastAssistantMessage({ experts: [...experts] });
                  const magg = experts.filter(e => e.coalition === "maggioranza").length;
                  const opp = experts.filter(e => e.coalition === "opposizione").length;
                  console.log(`[Pipeline] Step 3 result: ${experts.length} esperti (${magg} magg, ${opp} opp)`);
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 3,
                      label: "Esperti",
                      result: `${experts.length} esperti (${magg} magg., ${opp} opp.)`,
                      details: { experts: experts.length, maggioranza: magg, opposizione: opp }
                    }]
                  } : null);
                } else {
                  console.warn("[Pipeline] Step 3: experts payload is not an array", expertsPayload);
                }
                break;

              case "citations":
                const citationsPayload = data.data || data.citations;
                if (Array.isArray(citationsPayload)) {
                  citations = citationsPayload;
                  updateLastAssistantMessage({ citations: [...citations] });
                  console.log(`[Pipeline:Citations] Step 4: ${citations.length} interventi ricevuti, chunk_ids:`, citations.map(c => c.chunk_id));
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 4,
                      label: "Interventi",
                      result: `${citations.length} interventi rilevanti`,
                      details: { citations: citations.length }
                    }]
                  } : null);
                } else {
                  console.warn("[Pipeline:Citations] Step 4: payload is not an array", citationsPayload);
                }
                break;

              case "balance":
                balanceMetrics = {
                  maggioranzaPercentage: data.maggioranza_percentage,
                  opposizionePercentage: data.opposizione_percentage,
                  biasScore: data.bias_score,
                };
                console.log(`[Pipeline] Step 5: Magg ${data.maggioranza_percentage?.toFixed(1)}% / Opp ${data.opposizione_percentage?.toFixed(1)}% (bias: ${data.bias_score?.toFixed(2)})`);
                updateLastAssistantMessage({ balanceMetrics });
                setProgress((prev) => prev ? {
                  ...prev,
                  stepResults: [...prev.stepResults, {
                    step: 5,
                    label: "Statistiche",
                    result: `Magg. ${data.maggioranza_percentage?.toFixed(0)}% / Opp. ${data.opposizione_percentage?.toFixed(0)}%`,
                    details: balanceMetrics
                  }]
                } : null);
                break;

              case "compass":
                try {
                  compassData = data.data || data;
                  updateLastAssistantMessage({ compass: compassData });
                  console.log(`[Pipeline] Step 6: Compass — ${compassData.groups?.length || 0} gruppi, ${compassData.axes?.length || 0} assi`);
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 6,
                      label: "Bussola Ideologica",
                      result: "Analisi completata",
                      details: { axes: compassData.axes, groups: compassData.groups?.length }
                    }]
                  } : null);
                } catch(e) {
                   console.error("[Pipeline] Step 6: Compass error", e);
                }
                break;

              case "citation_details":
                const citDetailsPayload = data.data || data.citations;
                if (Array.isArray(citDetailsPayload)) {
                    const prevChunkIds = citations.map(c => c.chunk_id);
                    citations = citDetailsPayload;
                    updateLastAssistantMessage({ citations: [...citations] });
                    const newChunkIds = citations.map(c => c.chunk_id);
                    const added = newChunkIds.filter(id => !prevChunkIds.includes(id));
                    const removed = prevChunkIds.filter(id => !newChunkIds.includes(id));
                    console.log(`[Pipeline:Citations] Verified: ${citations.length} citations`, {
                      chunk_ids: newChunkIds,
                      speakers: citations.map(c => `${c.deputy_first_name} ${c.deputy_last_name}`),
                      added: added.length ? added : "none",
                      removed: removed.length ? removed : "none",
                    });
                } else {
                    console.warn("[Pipeline:Citations] citation_details payload is NOT an array:", citDetailsPayload);
                }
                break;

              case "chunk":
                accumulatedContent += (data.data || data.content || "");
                setStreamingContent(accumulatedContent);
                updateLastAssistantMessage({ content: accumulatedContent });

                setProgress((prev) => {
                  if (!prev) return null;
                  const alreadyDone = prev.stepResults.some(r => r.step === 7);
                  if (alreadyDone) return prev;
                  console.log(`[Pipeline] Step 7: First chunk received (streaming ${accumulatedContent.length} chars)`);
                  return {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 7,
                      label: "Generazione",
                      result: "Sintesi completata"
                    }]
                  };
                });
                break;

              case "complete":
                console.log(`[Pipeline] === COMPLETE ===`);
                console.log(`[Pipeline] Content: ${accumulatedContent.length} chars`);
                console.log(`[Pipeline:Citations] Final: ${citations.length} citations in sidebar`);

                // Extract citation links from generated text for cross-check
                const textCitLinks = (accumulatedContent.match(/\]\((leg1[89]_[^)]+)\)/g) || [])
                  .map((m: string) => m.slice(2, -1));
                const sidebarIds = new Set(citations.map(c => c.chunk_id));
                const unmatchedLinks = textCitLinks.filter((id: string) => !sidebarIds.has(id));
                if (unmatchedLinks.length > 0) {
                  console.warn(`[Pipeline:Citations] MISMATCH: ${unmatchedLinks.length} citation links in text not in sidebar:`, unmatchedLinks);
                } else if (textCitLinks.length > 0) {
                  console.log(`[Pipeline:Citations] All ${textCitLinks.length} text citation links matched in sidebar`);
                }

                console.log(`[Pipeline:Baseline] baseline_answer: type=${typeof data.baseline_answer}, len=${data.baseline_answer?.length ?? "N/A"}, error=${data.baseline_error || "none"}`);
                if (data.baseline_answer) {
                  console.log(`[Pipeline:Baseline] Preview: "${data.baseline_answer.substring(0, 150)}..."`);
                }
                console.log(`[Pipeline:Baseline] ab_assignment:`, data.ab_assignment);

                baselineAnswer = data.baseline_answer || "";
                abAssignment = data.ab_assignment || null;

                setProgress((prev) =>
                  prev ? { ...prev, isComplete: true } : null
                );
                updateLastAssistantMessage({
                  status: "complete",
                  content: accumulatedContent,
                  citations,
                  experts,
                  balanceMetrics,
                  baselineAnswer: baselineAnswer || undefined,
                  abAssignment: abAssignment || undefined,
                });

                // Log timing if available
                if (data.metadata?.timing) {
                  const timing = data.metadata.timing;
                  console.log(`[Pipeline] Timing breakdown (ms):`, timing);
                }

                // Save to history
                try {
                  const historyPayload = {
                    query: content,
                    answer: accumulatedContent,
                    citations,
                    experts,
                    balance: balanceMetrics ? {
                      maggioranza_percentage: balanceMetrics.maggioranzaPercentage,
                      opposizione_percentage: balanceMetrics.opposizionePercentage,
                      bias_score: balanceMetrics.biasScore,
                    } : null,
                    compass: compassData,
                    baseline_answer: baselineAnswer || null,
                    ab_assignment: abAssignment || null,
                  };

                  console.log(`[Pipeline:Baseline] Saving to history: baseline=${baselineAnswer ? baselineAnswer.length + " chars" : "null"}, ab=${abAssignment ? JSON.stringify(abAssignment) : "null"}`);

                  fetch(`${config.api.baseUrl}/history`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(historyPayload),
                  }).then((res) => {
                    if (res.ok) {
                      console.log("[Pipeline] History saved OK");
                    } else {
                      res.text().then(body => {
                        console.error("[Pipeline] History save failed:", res.status, body);
                      });
                    }
                  }).catch((err) => {
                    console.error("[Pipeline] History save error:", err);
                  });
                } catch (e) {
                  console.error("[Pipeline] History payload error:", e);
                }
                break;

              case "error":
                console.error(`[Pipeline] ERROR from server:`, data.message);
                throw new Error(data.message);

              default:
                console.log(`[Pipeline] Unknown event: "${data.type}"`, data);
            }
          } catch (parseError) {
            console.warn(`[Pipeline:Buffer] JSON parse error:`, parseError, `raw: "${line.substring(0, 200)}"`);
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        // Request was cancelled, ignore
        return;
      }

      const errorMessage = error instanceof Error ? error.message : "Errore sconosciuto";

      updateLastAssistantMessage({
        status: "error",
        content: `Mi dispiace, si è verificato un errore: ${errorMessage}`,
      });

      options.onError?.(error instanceof Error ? error : new Error(errorMessage));
    } finally {
      setIsLoading(false);
      setProgress(null);
      setStreamingContent("");
      abortControllerRef.current = null;
    }
  }, [isLoading, addUserMessage, updateLastAssistantMessage, options]);

  // Cancel current request
  const cancelRequest = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setProgress(null);
      setStreamingContent("");
    }
  }, []);

  // Clear all messages
  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  // Load a chat from history
  const loadChat = useCallback((historyData: any) => {
    // Clear current state
    setIsLoading(false);
    setProgress(null);
    setStreamingContent("");
    
    const userMsg: Message = {
      id: `user_${historyData.id}`,
      role: "user",
      content: historyData.query,
      timestamp: new Date(historyData.timestamp),
      status: "complete"
    };

    const assistantMsg: Message = {
      id: historyData.id,
      role: "assistant",
      content: historyData.answer,
      timestamp: new Date(historyData.timestamp),
      status: "complete",
      citations: historyData.citations,
      experts: historyData.experts,
      balanceMetrics: historyData.balance ? {
          maggioranzaPercentage: historyData.balance.maggioranza_percentage,
          opposizionePercentage: historyData.balance.opposizione_percentage,
          biasScore: historyData.balance.bias_score
      } : undefined,
      compass: historyData.compass,
      baselineAnswer: historyData.baseline_answer || undefined,
      abAssignment: historyData.ab_assignment || undefined,
    };

    setMessages([userMsg, assistantMsg]);
  }, []);

  return {
    messages,
    isLoading,
    progress,
    streamingContent,
    sendMessage,
    cancelRequest,
    clearMessages,
    addAssistantMessage,
    loadChat,
  };
}
