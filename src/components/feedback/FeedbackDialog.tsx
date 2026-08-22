"use client";

// Dialog post-voto: la versione compatta del survey /iswc. Si apre al
// click sul pollice; tutto è facoltativo, chiudere è sempre gratis.

import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { config } from "@/config";
import { cn } from "@/lib/utils";

const QUESTION_KEYS = ["q1", "q2", "q3", "q4"] as const;

type Answers = Partial<Record<(typeof QUESTION_KEYS)[number], number>>;

interface FeedbackDialogProps {
  open: boolean;
  onClose: () => void;
  tool: string;
  context?: string;
}

export function FeedbackDialog({ open, onClose, tool, context }: FeedbackDialogProps) {
  const tb = useTranslations("Booth");
  const tf = useTranslations("Feedback");
  const locale = useLocale();
  const [answers, setAnswers] = useState<Answers>({});
  const [comment, setComment] = useState("");

  const hasContent = Object.keys(answers).length > 0 || comment.trim().length > 0;

  const submit = useCallback(async () => {
    if (hasContent) {
      try {
        await fetch(`${config.api.baseUrl}/feedback/booth`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...answers,
            comment: comment.trim() || null,
            source: "widget",
            tool,
            context,
            locale,
          }),
        });
      } catch {
        // mai bloccare l'utente per un feedback
      }
    }
    onClose();
  }, [answers, comment, hasContent, tool, context, locale, onClose]);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md gap-0 p-6">
        <DialogHeader className="mb-4">
          <DialogTitle className="[font-family:var(--font-display)] text-xl font-medium tracking-tight text-left">
            {tf("dialogTitle")}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          {QUESTION_KEYS.map((key, i) => (
            <fieldset key={key}>
              <legend className="text-[13px] leading-5 text-foreground mb-2">
                <span className="[font-family:var(--font-display)] text-muted-foreground mr-1.5">{i + 1}.</span>
                {tb(key)}
              </legend>
              <div>
                <div className="flex justify-between gap-1.5">
                  {[1, 2, 3, 4, 5].map((v) => (
                    <button
                      key={v}
                      onClick={() => setAnswers((a) =>
                        a[key] === v ? { ...a, [key]: undefined } : { ...a, [key]: v })}
                      aria-label={`${v}/5`}
                      className={cn(
                        "h-8 flex-1 border text-[13px] tabular-nums transition-colors cursor-pointer",
                        answers[key] === v
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border text-muted-foreground hover:border-foreground hover:text-foreground",
                      )}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                  <span>{tb("scaleLow")}</span>
                  <span>{tb("scaleHigh")}</span>
                </div>
              </div>
            </fieldset>
          ))}

          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={2}
            placeholder={tb("commentPlaceholder")}
            className="w-full bg-transparent border border-border p-2.5 text-[13px] leading-5 text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-foreground transition-colors resize-none"
          />

          <div className="flex items-center gap-3">
            <button
              onClick={submit}
              className={cn(
                "flex-1 py-2.5 text-sm font-medium tracking-wide transition-colors cursor-pointer",
                hasContent
                  ? "bg-primary text-primary-foreground hover:bg-foreground"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {hasContent ? tb("submit") : tf("skip")}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
