"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type {
  Message,
  Citation,
  Expert,
  BalanceMetrics,
  ProcessingProgress,
  StepResult,
  TopicStatistics,
} from "@/types";
import type { CompassData } from "@/components/chat/CompassCard";
import { config } from "@/config";

interface UseChatOptions {
  onError?: (error: Error) => void;
}

export function useChat(options: UseChatOptions = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [lastCompletedProgress, setLastCompletedProgress] = useState<ProcessingProgress | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentTaskIdRef = useRef<string | null>(null);
  // Mobile reconnection: track query and retry count for silent re-send
  const queryContentRef = useRef<string>("");
  const retryCountRef = useRef(0);
  const streamCompletedRef = useRef(false);
  const sendMessageRef = useRef<((content: string, isRetry?: boolean) => Promise<void>) | null>(null);

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
  const sendMessage = useCallback(async (content: string, isRetry = false) => {
    if (!content.trim() || isLoading) return;

    // Abort any previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setStreamingContent("");
    streamCompletedRef.current = false;

    if (!isRetry) {
      // Fresh query: reset retry count
      retryCountRef.current = 0;
      setLastCompletedProgress(null);
    }

    // currentStep: 0 = "connecting" — wait for first SSE event before
    // showing pipeline or waiting view (avoids false "Step 1" display
    // when the query is actually queued on the backend).
    setProgress({
      currentStep: 0,
      totalSteps: config.ui.progressSteps.length,
      stepLabel: "Connessione...",
      stepDescription: "",
      isComplete: false,
      isWaiting: false,
      stepResults: [],
    });

    // Generate a task_id for reconnection support
    const taskId = `task_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    currentTaskIdRef.current = taskId;
    queryContentRef.current = content;

    // Reset messages: clear previous conversation and start fresh
    const userMessage: Message = {
      id: generateId(),
      role: "user",
      content,
      timestamp: new Date(),
      status: "complete",
    };
    const assistantMessage: Message = {
      id: generateId(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
      status: "streaming",
    };
    setMessages([userMessage, assistantMessage]);

    try {
      const response = await fetch(`${config.api.baseUrl}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: content, task_id: taskId }),
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
      let compassData: CompassData | undefined = undefined;
      let topicStats: TopicStatistics | undefined;
      let commissioni: any[] = [];
      // Accumulator for step results — survives React state batching race conditions
      const stepResultsMap = new Map<number, { step: number; label: string; result: string; details?: any }>();
      let buffer = ""; // Buffer per messaggi SSE parziali

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // Flush TextDecoder remaining bytes + process any buffered data
          buffer += decoder.decode();
          if (buffer.trim()) {
            const remainingLines = buffer.split("\n").filter((l: string) => l.startsWith("data: "));
            for (const line of remainingLines) {
              try {
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;
                const data = JSON.parse(jsonStr);
                if (data.type === "complete") {
                  setProgress((prev) => prev ? { ...prev, isComplete: true } : null);
                  updateLastAssistantMessage({
                    status: "complete",
                    content: accumulatedContent,
                    citations,
                    experts,
                    balanceMetrics,
                    topicStats,
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
              case "task_id":
                // Server confirmed the task ID
                break;

              case "waiting":
                setProgress({
                  currentStep: 0,
                  totalSteps: config.ui.progressSteps.length,
                  stepLabel: "In attesa...",
                  stepDescription: data.message || "Attualmente troppi utenti stanno utilizzando il sistema, aspetta...",
                  isComplete: false,
                  isWaiting: true,
                  waitingMessage: data.message,
                  queuePosition: data.queue_position,
                  activeCount: data.active_count,
                  elapsedSeconds: data.elapsed_seconds ?? 0,
                  stepResults: [],
                });
                break;

              case "progress":
                const stepIndex = data.step - 1;
                const step = config.ui.progressSteps[stepIndex];
                const totalSteps = data.total || config.ui.progressSteps.length;
                setProgress((prev) => {
                  // Only advance forward, never go backwards
                  const newStep = Math.max(prev?.currentStep || 0, data.step);
                  const newStepConfig = config.ui.progressSteps[newStep - 1];
                  // Build results: start from accumulator (source of truth) + any existing results
                  const resultsById = new Map<number, { step: number; label: string; result?: string; details?: any }>();
                  // Copy existing results
                  for (const r of (prev?.stepResults || [])) {
                    resultsById.set(r.step, r);
                  }
                  // Overlay accumulator (always wins — it has the real data)
                  for (const [step, result] of stepResultsMap) {
                    resultsById.set(step, result);
                  }
                  // Fill generic placeholders only for steps WITHOUT dedicated SSE events
                  const stepsWithDedicatedEvents = new Set([2, 3, 4, 5, 6]);
                  for (let s = 1; s < newStep; s++) {
                    if (!resultsById.has(s) && !stepsWithDedicatedEvents.has(s)) {
                      const stepCfg = config.ui.progressSteps[s - 1];
                      resultsById.set(s, {
                        step: s,
                        label: stepCfg?.label || `Step ${s}`,
                        result: stepCfg?.description || "Completato",
                      });
                    }
                  }
                  return {
                    currentStep: newStep,
                    totalSteps: data.total || config.ui.progressSteps.length,
                    stepLabel: newStepConfig?.label || data.message || "",
                    stepDescription: newStepConfig?.description || "",
                    isComplete: false,
                    stepResults: Array.from(resultsById.values()),
                  };
                });
                break;

              case "commissioni":
                const commList = data.commissioni || [];
                commissioni = commList;
                updateLastAssistantMessage({ commissioni: [...commList] });
                const commNames = commList.map((c: any) => c.nome || c.name || String(c)).slice(0, 3);
                // Save to accumulator so it survives React state batching
                const topComm = commList.length > 0 ? (commList[0].nome || commList[0].name || String(commList[0])) : null;
                const commResult = {
                  step: 2,
                  label: "Commissione",
                  result: topComm
                    ? `Trovata commissione competente: ${topComm}`
                    : "Nessuna commissione pertinente",
                  details: { commissioni: commList }
                };
                stepResultsMap.set(2, commResult);
                setProgress((prev) => {
                  if (!prev) return null;
                  const filtered = prev.stepResults.filter(r => r.step !== 2);
                  return {
                    ...prev,
                    stepResults: [...filtered, commResult]
                  };
                });
                break;

              case "experts":
                const expertsPayload = data.data || data.experts;
                if (Array.isArray(expertsPayload)) {
                  experts = expertsPayload;
                  updateLastAssistantMessage({ experts: [...experts] });
                  const magg = experts.filter(e => e.coalition === "maggioranza").length;
                  const opp = experts.filter(e => e.coalition === "opposizione").length;
                  const topExperts = experts.slice(0, 3).map(e => `${e.first_name} ${e.last_name}`).join(", ");
                  const expertsResult = {
                    step: 3,
                    label: "Esperti",
                    result: `${experts.length} esperti: ${topExperts}${experts.length > 3 ? "..." : ""} (${magg} maggioranza, ${opp} opposizione)`,
                    details: { experts: experts.length, maggioranza: magg, opposizione: opp }
                  };
                  stepResultsMap.set(3, expertsResult);
                  setProgress((prev) => {
                    if (!prev) return null;
                    const filtered = prev.stepResults.filter(r => r.step !== 3);
                    return {
                      ...prev,
                      stepResults: [...filtered, expertsResult]
                    };
                  });
                } else {
                }
                break;

              case "citations":
                const citationsPayload = data.data || data.citations;
                if (Array.isArray(citationsPayload)) {
                  citations = citationsPayload;
                  updateLastAssistantMessage({ citations: [...citations] });
                  const uniqueDeputies = [...new Set(citations.map(c => `${c.deputy_first_name} ${c.deputy_last_name}`))];
                  const deputyPreview = uniqueDeputies.slice(0, 3).join(", ");
                  const citationsResult = {
                    step: 4,
                    label: "Interventi",
                    result: `${citations.length} interventi di ${deputyPreview}${uniqueDeputies.length > 3 ? ` e altri ${uniqueDeputies.length - 3}` : ""}`,
                    details: { citations: citations.length }
                  };
                  stepResultsMap.set(4, citationsResult);
                  setProgress((prev) => {
                    if (!prev) return null;
                    const filtered = prev.stepResults.filter(r => r.step !== 4);
                    return {
                      ...prev,
                      stepResults: [...filtered, citationsResult]
                    };
                  });
                } else {
                }
                break;

              case "balance":
                balanceMetrics = {
                  maggioranzaPercentage: data.maggioranza_percentage,
                  opposizionePercentage: data.opposizione_percentage,
                  biasScore: data.bias_score,
                };
                updateLastAssistantMessage({ balanceMetrics });
                const balanceResult = {
                  step: 5,
                  label: "Statistiche",
                  result: `Maggioranza ${data.maggioranza_percentage?.toFixed(0)}% / Opposizione ${data.opposizione_percentage?.toFixed(0)}%`,
                  details: balanceMetrics
                };
                stepResultsMap.set(5, balanceResult);
                setProgress((prev) => {
                  if (!prev) return null;
                  // Advance stepper to at least step 6 (balance = step 5 complete)
                  const nextStep = Math.max(prev.currentStep, 6);
                  const stepConfig = config.ui.progressSteps[nextStep - 1];
                  return {
                    ...prev,
                    currentStep: nextStep,
                    stepLabel: stepConfig?.label || prev.stepLabel,
                    stepDescription: stepConfig?.description || prev.stepDescription,
                    stepResults: [...prev.stepResults.filter(r => r.step !== 5), balanceResult]
                  };
                });
                break;

              case "compass":
                try {
                  compassData = data.data || data;
                  if (!compassData) break;
                  updateLastAssistantMessage({ compass: compassData });
                  const compassResult = {
                    step: 6,
                    label: "Bussola Ideologica",
                    result: `${compassData.groups?.length || 0} gruppi posizionati su ${Object.keys(compassData.axes || {}).length} assi tematici`,
                    details: { axes: compassData.axes, groups: compassData.groups?.length }
                  };
                  stepResultsMap.set(6, compassResult);
                  setProgress((prev) => {
                    if (!prev) return null;
                    // Advance stepper to at least step 7 (compass = step 6 complete)
                    const nextStep = Math.max(prev.currentStep, 7);
                    const stepConfig = config.ui.progressSteps[nextStep - 1];
                    return {
                      ...prev,
                      currentStep: nextStep,
                      stepLabel: stepConfig?.label || prev.stepLabel,
                      stepDescription: stepConfig?.description || prev.stepDescription,
                      stepResults: [...prev.stepResults.filter(r => r.step !== 6), compassResult]
                    };
                  });
                } catch(e) {
                   console.error("[Pipeline] Step 6: Compass error", e);
                }
                break;

              case "topic_stats":
                topicStats = data as TopicStatistics;
                updateLastAssistantMessage({ topicStats });
                break;

              case "citation_details":
                const citDetailsPayload = data.data || data.citations;
                if (Array.isArray(citDetailsPayload)) {
                    citations = citDetailsPayload;
                    updateLastAssistantMessage({ citations: [...citations] });
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
                  // Advance stepper to step 7 and mark it as completing
                  const stepConfig = config.ui.progressSteps[6]; // step 7 (0-indexed)
                  return {
                    ...prev,
                    currentStep: 7,
                    stepLabel: stepConfig?.label || "Generazione",
                    stepDescription: "Scrittura in corso...",
                    stepResults: [...prev.stepResults, {
                      step: 7,
                      label: "Generazione",
                      result: "Sintesi completata"
                    }]
                  };
                });
                break;

              case "complete":

                // Extract citation links from generated text for cross-check
                const textCitLinks = (accumulatedContent.match(/\]\((leg1[89]_[^)]+)\)/g) || [])
                  .map((m: string) => m.slice(2, -1));
                const sidebarIds = new Set(citations.map(c => c.chunk_id));
                const unmatchedLinks = textCitLinks.filter((id: string) => !sidebarIds.has(id));
                if (unmatchedLinks.length > 0) {
                } else if (textCitLinks.length > 0) {
                }

                // Mark step 8 as complete and finalize progress
                setProgress((prev) => {
                  if (!prev) return null;
                  // Merge accumulator results (source of truth for dedicated events)
                  const resultsById = new Map<number, any>();
                  for (const r of prev.stepResults) resultsById.set(r.step, r);
                  for (const [step, result] of stepResultsMap) resultsById.set(step, result);
                  const newResults = Array.from(resultsById.values());
                  if (!newResults.some(r => r.step === 8)) {
                    newResults.push({
                      step: 8,
                      label: "Valutazione",
                      result: "Completata",
                    });
                  }
                  return { ...prev, isComplete: true, stepResults: newResults };
                });
                // Mark stream as completed — no retry needed
                streamCompletedRef.current = true;

                updateLastAssistantMessage({
                  status: "complete",
                  content: accumulatedContent,
                  citations,
                  experts,
                  balanceMetrics,
                  topicStats,
                });

                // Log timing if available
                if (data.metadata?.timing) {
                  const timing = data.metadata.timing;
                }

                // Save to history
                try {
                  const historyPayload = {
                    query: content,
                    answer: accumulatedContent,
                    citations,
                    experts,
                    commissioni,
                    balance: balanceMetrics ? {
                      maggioranza_percentage: balanceMetrics.maggioranzaPercentage,
                      opposizione_percentage: balanceMetrics.opposizionePercentage,
                      bias_score: balanceMetrics.biasScore,
                    } : null,
                    compass: compassData,
                    topic_stats: topicStats || null,
                  };

                  fetch(`${config.api.baseUrl}/history`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(historyPayload),
                  }).then(async (res) => {
                    if (res.ok) {
                      const savedChat = await res.json();
                      updateLastAssistantMessage({ chatId: savedChat.id });
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
            }
          } catch (parseError) {
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        // Request was cancelled by user, ignore
        return;
      }


      // If stream didn't complete and we can retry, do a silent re-send
      if (!streamCompletedRef.current && retryCountRef.current < 2) {
        retryCountRef.current++;
        const savedQuery = queryContentRef.current;
        setIsLoading(false);
        abortControllerRef.current = null;
        // Re-send after a brief delay
        setTimeout(() => sendMessageRef.current?.(savedQuery, true), 300);
        return;
      }

      // Max retries exhausted — show error
      const errorMessage = error instanceof Error ? error.message : "Errore sconosciuto";
      updateLastAssistantMessage({
        status: "error",
        content: `Mi dispiace, si è verificato un errore: ${errorMessage}`,
      });
      options.onError?.(error instanceof Error ? error : new Error(errorMessage));
    } finally {
      // If stream ended without "complete" (e.g. mobile browser killed connection)
      // and we haven't exhausted retries, do a silent re-send
      if (!streamCompletedRef.current && retryCountRef.current < 2) {
        retryCountRef.current++;
        const savedQuery = queryContentRef.current;
        setIsLoading(false);
        setStreamingContent("");
        abortControllerRef.current = null;
        setTimeout(() => sendMessageRef.current?.(savedQuery, true), 300);
        return;
      }

      // Normal completion or retries exhausted
      setProgress((prev) => {
        if (prev) {
          setLastCompletedProgress(prev);
        }
        return null;
      });
      setIsLoading(false);
      setStreamingContent("");
      abortControllerRef.current = null;
    }
  }, [isLoading, addUserMessage, updateLastAssistantMessage, options]);

  // Keep a ref to sendMessage for silent retry from catch/finally
  sendMessageRef.current = sendMessage;

  // Visibility change handler: if user returns and stream was interrupted, retry
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (
        document.visibilityState === "visible" &&
        !streamCompletedRef.current &&
        queryContentRef.current &&
        !isLoading &&
        retryCountRef.current < 2
      ) {
        retryCountRef.current++;
        const savedQuery = queryContentRef.current;
        sendMessageRef.current?.(savedQuery, true);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [isLoading]);

  // Cancel current request
  const cancelRequest = useCallback(() => {
    // 1. Abort the SSE/fetch connection immediately
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // 2. Tell the backend to stop the pipeline (fire-and-forget)
    const taskId = currentTaskIdRef.current;
    if (taskId) {
      fetch(`${config.api.baseUrl}/chat/task/${taskId}`, { method: "DELETE" }).catch(() => {
        // Ignore — if the request fails the task will just complete normally
      });
      currentTaskIdRef.current = null;
    }

    // 3. Prevent mobile-reconnect retry
    streamCompletedRef.current = true;
    retryCountRef.current = 2;

    // 4. Reset UI
    setIsLoading(false);
    setProgress(null);
    setStreamingContent("");
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
      topicStats: historyData.topic_stats || undefined,
      chatId: historyData.id,
    };

    setMessages([userMsg, assistantMsg]);

    // Rebuild a synthetic completed progress from available data
    const stepResults: { step: number; label: string; result: string; details?: any }[] = [];
    stepResults.push({ step: 1, label: "Analisi query", result: "Completata" });

    if (historyData.citations?.length) {
      const uniqueDeputies = [...new Set(historyData.citations.map((c: any) => `${c.deputy_first_name} ${c.deputy_last_name}`))];
      stepResults.push({
        step: 4,
        label: "Interventi",
        result: `${historyData.citations.length} interventi di ${uniqueDeputies.slice(0, 3).join(", ")}${uniqueDeputies.length > 3 ? ` e altri ${uniqueDeputies.length - 3}` : ""}`,
        details: { citations: historyData.citations.length },
      });
    }
    if (historyData.experts?.length) {
      const magg = historyData.experts.filter((e: any) => e.coalition === "maggioranza").length;
      const opp = historyData.experts.filter((e: any) => e.coalition === "opposizione").length;
      const topExperts = historyData.experts.slice(0, 3).map((e: any) => `${e.first_name} ${e.last_name}`).join(", ");
      stepResults.push({
        step: 3,
        label: "Esperti",
        result: `${historyData.experts.length} esperti: ${topExperts}${historyData.experts.length > 3 ? "..." : ""} (${magg} maggioranza, ${opp} opposizione)`,
        details: { experts: historyData.experts.length, maggioranza: magg, opposizione: opp },
      });
    }
    if (historyData.balance) {
      stepResults.push({
        step: 5,
        label: "Statistiche",
        result: `Maggioranza ${historyData.balance.maggioranza_percentage?.toFixed(0)}% / Opposizione ${historyData.balance.opposizione_percentage?.toFixed(0)}%`,
        details: historyData.balance,
      });
    }
    if (historyData.compass) {
      stepResults.push({
        step: 6,
        label: "Bussola Ideologica",
        result: `${historyData.compass.groups?.length || 0} gruppi posizionati`,
        details: { groups: historyData.compass.groups?.length },
      });
    }
    stepResults.push({ step: 7, label: "Generazione", result: "Sintesi completata" });
    stepResults.push({ step: 8, label: "Valutazione", result: "Completata" });

    setLastCompletedProgress({
      currentStep: config.ui.progressSteps.length,
      totalSteps: config.ui.progressSteps.length,
      stepLabel: "Completato",
      stepDescription: "",
      isComplete: true,
      stepResults,
    });
  }, []);

  return {
    messages,
    isLoading,
    progress,
    lastCompletedProgress,
    streamingContent,
    sendMessage,
    cancelRequest,
    clearMessages,
    addAssistantMessage,
    loadChat,
  };
}
