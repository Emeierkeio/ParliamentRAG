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
       // Logging temporaneo
       const existingIds = prev.map(m => m.id);
       console.log("[useChat] Existing IDs:", existingIds);
       console.log("[useChat] Incoming User Msg ID:", newMessage.id);

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
      // Logging temporaneo richiesto per debug
      const existingIds = prev.map(m => m.id);
      console.log("[useChat] Existing IDs:", existingIds);
      console.log("[useChat] Incoming Assistant Msg ID:", newMessage.id);
      
      // Deduplicazione
      if (prev.some(m => m.id === newMessage.id)) {
        console.warn("[useChat] Detected duplicate message ID, skipping add:", newMessage.id);
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
        if (done) break;

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
            console.log("[SSE] Received event:", data.type, data);

            switch (data.type) {
              case "progress":
                const stepIndex = data.step - 1;
                const step = config.ui.progressSteps[stepIndex];
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
                // Step 2 result: commissioni trovate
                const commList = data.commissioni || [];
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
                // Step 3 result: esperti identificati
                const expertsPayload = data.data || data.experts;
                if (Array.isArray(expertsPayload)) {
                  experts = expertsPayload;
                  updateLastAssistantMessage({ experts: [...experts] });
                  const magg = experts.filter(e => e.coalition === "maggioranza").length;
                  const opp = experts.filter(e => e.coalition === "opposizione").length;
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 3,
                      label: "Esperti",
                      result: `${experts.length} esperti (${magg} magg., ${opp} opp.)`,
                      details: { experts: experts.length, maggioranza: magg, opposizione: opp }
                    }]
                  } : null);
                }
                break;

              case "citations":
                // Step 4 result: citazioni trovate
                const citationsPayload = data.data || data.citations;
                if (Array.isArray(citationsPayload)) {
                  console.log("[useChat] Citation sample:", JSON.stringify(citationsPayload[0]));
                  citations = citationsPayload;
                  updateLastAssistantMessage({ citations: [...citations] });
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 4,
                      label: "Interventi",
                      result: `${citations.length} interventi rilevanti`,
                      details: { citations: citations.length }
                    }]
                  } : null);
                }
                break;

              case "balance":
                // Step 5 result: metriche di bilanciamento
                balanceMetrics = {
                  maggioranzaPercentage: data.maggioranza_percentage,
                  opposizionePercentage: data.opposizione_percentage,
                  biasScore: data.bias_score,
                };
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
                // Step 6 result: Compass analysis
                try {
                  // The payload is in data.data (from backend) or data itself
                  compassData = data.data || data;
                  updateLastAssistantMessage({ compass: compassData });
                  
                  setProgress((prev) => prev ? {
                    ...prev,
                    stepResults: [...prev.stepResults, {
                      step: 6,
                      label: "Bussola Ideologica",
                      result: "Analisi completata",
                      details: { axes: compassData.axes, groups: compassData.groups?.length }
                    }]
                  } : null);
                  console.log("[useChat] Compass data received");
                } catch(e) {
                   console.error("Error handling compass data", e);
                }
                break;

              case "citation_details":
                // Step 7 result: citazioni verificate e arricchite con testo completo
                const citDetailsPayload = data.data || data.citations;
                if (Array.isArray(citDetailsPayload)) {
                    citations = citDetailsPayload;
                    updateLastAssistantMessage({ citations: [...citations] });
                    console.log("[useChat] Updated verified citations:", citations.length);
                    console.log("[useChat] Citation chunk_ids:", citations.map(c => c.chunk_id));
                    console.log("[useChat] Citation speakers:", citations.map(c => `${c.deputy_first_name} ${c.deputy_last_name}`));
                } else {
                    console.warn("[useChat] citation_details payload is NOT an array:", citDetailsPayload);
                }
                break;

              case "chunk":
                accumulatedContent += (data.data || data.content || "");
                setStreamingContent(accumulatedContent);
                updateLastAssistantMessage({ content: accumulatedContent });
                
                // On first chunk, mark Step 7 as complete in history
                setProgress((prev) => {
                  if (!prev) return null;
                  const alreadyDone = prev.stepResults.some(r => r.step === 7);
                  if (alreadyDone) return prev;
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
                // Extract baseline data from complete event
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

                // Save to history
                try {
                  fetch(`${config.api.baseUrl}/history`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
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
                    }),
                  }).then((res) => {
                    if (res.ok) {
                      console.log("[useChat] Chat saved to history");
                    } else {
                      console.error("[useChat] Failed to save to history:", res.status, res.statusText);
                    }
                  }).catch((err) => {
                    console.error("[useChat] Failed to save to history:", err);
                  });
                } catch (e) {
                  console.error("[useChat] Error saving to history:", e);
                }
                break;

              case "error":
                throw new Error(data.message);

              default:
                console.log("SSE event:", data.type, data);
            }
          } catch (parseError) {
            // Skip invalid JSON lines
            console.warn("Failed to parse SSE data:", parseError);
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
