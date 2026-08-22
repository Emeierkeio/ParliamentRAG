"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ThumbsUp, ThumbsDown, X, ArrowRight } from "lucide-react";
import { config } from "@/config";
import { cn } from "@/lib/utils";

// Quiet per-tool feedback: one thumb, one optional comment, then it leaves.
// Reappears only after 60 days (voted) or 14 days (dismissed).

const GIVEN_TTL_MS = 60 * 24 * 60 * 60 * 1000;
const DISMISSED_TTL_MS = 14 * 24 * 60 * 60 * 1000;

type Stage = "idle" | "comment" | "thanks" | "hidden";

function storageKey(tool: string) {
  return `prag-feedback:${tool}`;
}

function isSnoozed(tool: string): boolean {
  try {
    const raw = localStorage.getItem(storageKey(tool));
    if (!raw) return false;
    const { status, at } = JSON.parse(raw);
    const ttl = status === "given" ? GIVEN_TTL_MS : DISMISSED_TTL_MS;
    return Date.now() - at < ttl;
  } catch {
    return false;
  }
}

function snooze(tool: string, status: "given" | "dismissed") {
  try {
    localStorage.setItem(storageKey(tool), JSON.stringify({ status, at: Date.now() }));
  } catch {
    // storage pieno o bloccato: il widget si ripresenterà, pazienza
  }
}

interface FeedbackPulseProps {
  tool: "chat" | "search" | "ranking" | "compass" | "timeline" | "explorer" | "data";
  context?: string;
  className?: string;
}

export function FeedbackPulse({ tool, context, className }: FeedbackPulseProps) {
  const t = useTranslations("Feedback");
  const locale = useLocale();
  const [stage, setStage] = useState<Stage>("hidden");
  const [comment, setComment] = useState("");
  const feedbackIdRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setStage(isSnoozed(tool) ? "hidden" : "idle");
  }, [tool]);

  useEffect(() => {
    if (stage === "comment") inputRef.current?.focus();
    if (stage === "thanks") {
      const timer = setTimeout(() => setStage("hidden"), 2500);
      return () => clearTimeout(timer);
    }
  }, [stage]);

  const vote = useCallback(async (value: "up" | "down") => {
    snooze(tool, "given");
    setStage("comment");
    try {
      const res = await fetch(`${config.api.baseUrl}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, vote: value, context, locale }),
      });
      if (res.ok) feedbackIdRef.current = (await res.json()).id;
    } catch {
      // il voto si perde in silenzio: mai bloccare l'utente per un feedback
    }
  }, [tool, context, locale]);

  const sendComment = useCallback(async () => {
    const text = comment.trim();
    setStage("thanks");
    if (!text || !feedbackIdRef.current) return;
    try {
      await fetch(`${config.api.baseUrl}/feedback/${feedbackIdRef.current}/comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: text }),
      });
    } catch {
      // come sopra
    }
  }, [comment]);

  const dismiss = useCallback(() => {
    snooze(tool, "dismissed");
    setStage("hidden");
  }, [tool]);

  if (stage === "hidden") return null;

  return (
    <div
      className={cn(
        "group/fb mt-6 pt-3 border-t border-border/60 text-[13px] text-muted-foreground",
        className,
      )}
    >
      {stage === "idle" && (
        <div className="flex items-center gap-4">
          <span>{t("prompt")}</span>
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => vote("up")}
              aria-label={t("voteUpAria")}
              className="p-1 -m-1 text-muted-foreground/70 hover:text-foreground transition-all duration-150 hover:-translate-y-0.5 cursor-pointer"
            >
              <ThumbsUp className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
            <button
              onClick={() => vote("down")}
              aria-label={t("voteDownAria")}
              className="p-1 -m-1 text-muted-foreground/70 hover:text-foreground transition-all duration-150 hover:translate-y-0.5 cursor-pointer"
            >
              <ThumbsDown className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
          </div>
          <button
            onClick={dismiss}
            aria-label={t("dismissAria")}
            className="ml-auto p-1 -m-1 text-muted-foreground/0 group-hover/fb:text-muted-foreground/60 hover:!text-foreground transition-colors cursor-pointer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {stage === "comment" && (
        <form
          className="flex items-center gap-3"
          onSubmit={(e) => { e.preventDefault(); sendComment(); }}
        >
          <input
            ref={inputRef}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={500}
            placeholder={t("placeholder")}
            className="flex-1 min-w-0 bg-transparent border-0 border-b border-border pb-1 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-foreground transition-colors"
          />
          <button
            type="submit"
            className="group/send inline-flex items-center gap-1 whitespace-nowrap border-b border-border pb-0.5 hover:border-primary hover:text-primary transition-colors cursor-pointer"
          >
            {comment.trim() ? t("send") : t("skip")}
            <ArrowRight className="h-3 w-3 transition-transform group-hover/send:translate-x-0.5" />
          </button>
        </form>
      )}

      {stage === "thanks" && (
        <p className="animate-in fade-in duration-300">{t("thanks")}</p>
      )}
    </div>
  );
}

// Per-answer thumbs for the chat: always visible, no snooze. The chosen
// thumb stays filled after the vote; the optional comment appears once.

type AnswerStage = "idle" | "comment" | "done";

export function AnswerFeedback({ context, className }: { context?: string; className?: string }) {
  const t = useTranslations("Feedback");
  const locale = useLocale();
  const [stage, setStage] = useState<AnswerStage>("idle");
  const [voted, setVoted] = useState<"up" | "down" | null>(null);
  const [comment, setComment] = useState("");
  const [showThanks, setShowThanks] = useState(false);
  const feedbackIdRef = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (stage === "comment") inputRef.current?.focus();
  }, [stage]);

  useEffect(() => {
    if (!showThanks) return;
    const timer = setTimeout(() => setShowThanks(false), 2500);
    return () => clearTimeout(timer);
  }, [showThanks]);

  const vote = useCallback(async (value: "up" | "down") => {
    setVoted(value);
    setStage("comment");
    try {
      const res = await fetch(`${config.api.baseUrl}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "chat", vote: value, context, locale }),
      });
      if (res.ok) feedbackIdRef.current = (await res.json()).id;
    } catch {
      // mai bloccare l'utente per un feedback
    }
  }, [context, locale]);

  const sendComment = useCallback(async () => {
    const text = comment.trim();
    setStage("done");
    setShowThanks(true);
    if (!text || !feedbackIdRef.current) return;
    try {
      await fetch(`${config.api.baseUrl}/feedback/${feedbackIdRef.current}/comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: text }),
      });
    } catch {
      // come sopra
    }
  }, [comment]);

  return (
    <div className={cn("mt-3 text-[13px] text-muted-foreground", className)}>
      <div className="flex items-center gap-2.5">
        <button
          onClick={() => stage === "idle" && vote("up")}
          disabled={stage !== "idle"}
          aria-label={t("voteUpAria")}
          className={cn(
            "p-1 -m-1 transition-all duration-150",
            voted === "up"
              ? "text-foreground"
              : "text-muted-foreground/50",
            stage === "idle" && "hover:text-foreground hover:-translate-y-0.5 cursor-pointer",
            voted === "down" && "opacity-30",
          )}
        >
          <ThumbsUp className={cn("h-3.5 w-3.5", voted === "up" && "fill-current")} strokeWidth={1.75} />
        </button>
        <button
          onClick={() => stage === "idle" && vote("down")}
          disabled={stage !== "idle"}
          aria-label={t("voteDownAria")}
          className={cn(
            "p-1 -m-1 transition-all duration-150",
            voted === "down"
              ? "text-foreground"
              : "text-muted-foreground/50",
            stage === "idle" && "hover:text-foreground hover:translate-y-0.5 cursor-pointer",
            voted === "up" && "opacity-30",
          )}
        >
          <ThumbsDown className={cn("h-3.5 w-3.5", voted === "down" && "fill-current")} strokeWidth={1.75} />
        </button>
        {showThanks && <span className="animate-in fade-in duration-300">{t("thanks")}</span>}
      </div>

      {stage === "comment" && (
        <form
          className="mt-2 flex items-center gap-3 max-w-md"
          onSubmit={(e) => { e.preventDefault(); sendComment(); }}
        >
          <input
            ref={inputRef}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={500}
            placeholder={t("placeholder")}
            className="flex-1 min-w-0 bg-transparent border-0 border-b border-border pb-1 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-foreground transition-colors"
          />
          <button
            type="submit"
            className="group/send inline-flex items-center gap-1 whitespace-nowrap border-b border-border pb-0.5 hover:border-primary hover:text-primary transition-colors cursor-pointer"
          >
            {comment.trim() ? t("send") : t("skip")}
            <ArrowRight className="h-3 w-3 transition-transform group-hover/send:translate-x-0.5" />
          </button>
        </form>
      )}
    </div>
  );
}
