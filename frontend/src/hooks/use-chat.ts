"use client";

import { useState, useCallback, useRef } from "react";
import type {
  Message,
  Citation,
  Expert,
  BalanceMetrics,
  ProcessingProgress,
  StepResult,
  TopicStatistics,
} from "@/types";
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
    setLastCompletedProgress(null);
    setProgress({
      currentStep: 1,
      totalSteps: config.ui.progressSteps.length,
      stepLabel: config.ui.progressSteps[0].label,
      stepDescription: config.ui.progressSteps[0].description,
      isComplete: false,
      stepResults: [],
    });

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
      let topicStats: TopicStatistics | undefined;
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
                    topicStats,
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
                const totalSteps = data.total || config.ui.progressSteps.length;
                console.log(`[Pipeline] Step ${data.step}/${totalSteps}: ${step?.label || data.message}`);
                setProgress((prev) => {
                  // Only advance forward, never go backwards
                  const newStep = Math.max(prev?.currentStep || 0, data.step);
                  const newStepConfig = config.ui.progressSteps[newStep - 1];
                  const newResults = [...(prev?.stepResults || [])];
                  // Mark all completed steps that don't have a result yet
                  for (let s = 1; s < newStep; s++) {
                    if (!newResults.some(r => r.step === s)) {
                      const stepCfg = config.ui.progressSteps[s - 1];
                      newResults.push({
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
                    stepResults: newResults,
                  };
                });
                break;

              case "commissioni":
                const commList = data.commissioni || [];
                const commNames = commList.map((c: any) => c.nome || c.name || String(c)).slice(0, 3);
                console.log(`[Pipeline] Step 2 result: ${commList.length} commissioni`, commNames);
                setProgress((prev) => {
                  if (!prev) return null;
                  // Replace any existing step 2 result with actual commission names
                  const filtered = prev.stepResults.filter(r => r.step !== 2);
                  return {
                    ...prev,
                    stepResults: [...filtered, {
                      step: 2,
                      label: "Commissioni",
                      result: commNames.length > 0 ? commNames.join(", ") : `${commList.length} commissioni pertinenti`,
                      details: { commissioni: commList }
                    }]
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
                  console.log(`[Pipeline] Step 3 result: ${experts.length} esperti (${magg} magg, ${opp} opp)`);
                  const topExperts = experts.slice(0, 3).map(e => `${e.first_name} ${e.last_name}`).join(", ");
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 3,
                      label: "Esperti",
                      result: `${experts.length} esperti: ${topExperts}${experts.length > 3 ? "..." : ""} (${magg} magg., ${opp} opp.)`,
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
                  const uniqueDeputies = [...new Set(citations.map(c => `${c.deputy_first_name} ${c.deputy_last_name}`))];
                  const deputyPreview = uniqueDeputies.slice(0, 3).join(", ");
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 4,
                      label: "Interventi",
                      result: `${citations.length} interventi di ${deputyPreview}${uniqueDeputies.length > 3 ? ` e altri ${uniqueDeputies.length - 3}` : ""}`,
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
                    stepResults: [...prev.stepResults, {
                      step: 5,
                      label: "Statistiche",
                      result: `Magg. ${data.maggioranza_percentage?.toFixed(0)}% / Opp. ${data.opposizione_percentage?.toFixed(0)}%`,
                      details: balanceMetrics
                    }]
                  };
                });
                break;

              case "compass":
                try {
                  compassData = data.data || data;
                  updateLastAssistantMessage({ compass: compassData });
                  console.log(`[Pipeline] Step 6: Compass — ${compassData.groups?.length || 0} gruppi, ${compassData.axes?.length || 0} assi`);
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
                      stepResults: [...prev.stepResults, {
                        step: 6,
                        label: "Bussola Ideologica",
                        result: `${compassData.groups?.length || 0} gruppi posizionati su ${Object.keys(compassData.axes || {}).length} assi tematici`,
                        details: { axes: compassData.axes, groups: compassData.groups?.length }
                      }]
                    };
                  });
                } catch(e) {
                   console.error("[Pipeline] Step 6: Compass error", e);
                }
                break;

              case "topic_stats":
                topicStats = data as TopicStatistics;
                updateLastAssistantMessage({ topicStats });
                console.log(`[Pipeline] Topic stats: ${topicStats.intervention_count} interventions, ${topicStats.speaker_count} speakers, ${topicStats.sessions_detail?.length || 0} sessions`);
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

              case "baseline":
                // Dedicated baseline event — arrives before "complete"
                baselineAnswer = data.baseline_answer || "";
                abAssignment = data.ab_assignment || null;
                console.log(`[Pipeline:Baseline] Received dedicated event: type=${typeof data.baseline_answer}, len=${data.baseline_answer?.length ?? "N/A"}, error=${data.baseline_error || "none"}`);
                if (data.baseline_answer) {
                  console.log(`[Pipeline:Baseline] Preview: "${data.baseline_answer.substring(0, 150)}..."`);
                }
                console.log(`[Pipeline:Baseline] ab_assignment:`, data.ab_assignment);

                // Mark step 8 (Baseline) as complete in progress stepper
                setProgress((prev) => {
                  if (!prev) return null;
                  const alreadyDone = prev.stepResults.some(r => r.step === 8);
                  if (alreadyDone) return prev;
                  return {
                    ...prev,
                    currentStep: 9,
                    stepLabel: config.ui.progressSteps[8]?.label || "Valutazione",
                    stepDescription: config.ui.progressSteps[8]?.description || "",
                    stepResults: [...prev.stepResults, {
                      step: 8,
                      label: "Baseline",
                      result: data.baseline_error
                        ? "Non disponibile"
                        : `${(data.baseline_answer?.length || 0)} caratteri generati`,
                    }]
                  };
                });
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

                // Fallback: pick up baseline from complete event if the
                // dedicated "baseline" event was missed (backward compat)
                if (!baselineAnswer && data.baseline_answer) {
                  baselineAnswer = data.baseline_answer;
                  abAssignment = data.ab_assignment || null;
                  console.log(`[Pipeline:Baseline] Recovered from complete event: ${baselineAnswer.length} chars`);
                }
                console.log(`[Pipeline:Baseline] baseline_answer: type=${typeof baselineAnswer}, len=${baselineAnswer?.length ?? "N/A"}, error=${data.baseline_error || "none"}`);
                console.log(`[Pipeline:Baseline] ab_assignment:`, abAssignment);

                // Mark step 9 as complete and finalize progress
                setProgress((prev) => {
                  if (!prev) return null;
                  const newResults = [...prev.stepResults];
                  // Ensure step 8 is marked complete (fallback if baseline event was missed)
                  if (!newResults.some(r => r.step === 8)) {
                    newResults.push({
                      step: 8,
                      label: "Baseline",
                      result: baselineAnswer ? "Completata" : "Non disponibile",
                    });
                  }
                  if (!newResults.some(r => r.step === 9)) {
                    newResults.push({
                      step: 9,
                      label: "Valutazione",
                      result: "Completata",
                    });
                  }
                  return { ...prev, isComplete: true, stepResults: newResults };
                });
                updateLastAssistantMessage({
                  status: "complete",
                  content: accumulatedContent,
                  citations,
                  experts,
                  balanceMetrics,
                  topicStats,
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
                    topic_stats: topicStats || null,
                    baseline_answer: baselineAnswer || null,
                    ab_assignment: abAssignment || null,
                  };

                  console.log(`[Pipeline:Baseline] Saving to history: baseline=${baselineAnswer ? baselineAnswer.length + " chars" : "null"}, ab=${abAssignment ? JSON.stringify(abAssignment) : "null"}`);

                  fetch(`${config.api.baseUrl}/history`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(historyPayload),
                  }).then(async (res) => {
                    if (res.ok) {
                      const savedChat = await res.json();
                      console.log("[Pipeline] History saved OK, id:", savedChat.id);
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
      // Save completed progress before clearing
      setProgress((prev) => {
        if (prev) setLastCompletedProgress(prev);
        return null;
      });
      setIsLoading(false);
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
      topicStats: historyData.topic_stats || undefined,
      baselineAnswer: historyData.baseline_answer || undefined,
      abAssignment: historyData.ab_assignment || undefined,
      chatId: historyData.id,
    };

    setMessages([userMsg, assistantMsg]);
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
