"use client";

import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { REASONS, type Reason, type Vote } from "./api";

export interface AnswerFeedbackPayload {
  reasons: Reason[];
  comment: string;
  email: string | null;
}

interface AnswerFeedbackDialogProps {
  open: boolean;
  vote: Vote | null;
  showNewsletter: boolean;
  onVote: (vote: Vote) => void;
  onSubmit: (payload: AnswerFeedbackPayload) => Promise<"ok" | "email_failed">;
  onClose: () => void;
}

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function AnswerFeedbackDialog({
  open,
  vote,
  showNewsletter,
  onVote,
  onSubmit,
  onClose,
}: AnswerFeedbackDialogProps) {
  const t = useTranslations("AnswerFeedback");
  const ids = useId();
  const [reasons, setReasons] = useState<Reason[]>([]);
  const [comment, setComment] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const trimmedEmail = email.trim();
  const canSubmit = !sending && (vote !== null || trimmedEmail.length > 0);

  const toggleReason = (r: Reason) =>
    setReasons((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const submit = async () => {
    setError(null);
    if (trimmedEmail) {
      if (!EMAIL_RE.test(trimmedEmail)) {
        setError(t("errorEmail"));
        return;
      }
      if (!consent) {
        setError(t("errorConsent"));
        return;
      }
    }
    setSending(true);
    const result = await onSubmit({
      reasons: vote === "down" ? reasons : [],
      comment: comment.trim(),
      email: trimmedEmail || null,
    });
    setSending(false);
    if (result === "email_failed") {
      setError(t("errorServer"));
      return;
    }
    onClose();
  };

  const voteButton = (value: Vote) => {
    const Icon = value === "up" ? ThumbsUp : ThumbsDown;
    const selected = vote === value;
    return (
      <button
        type="button"
        onClick={() => onVote(value)}
        aria-pressed={selected}
        className={cn(
          "flex items-center justify-center gap-2 h-11 border text-sm transition-colors cursor-pointer",
          "active:scale-[0.98]",
          selected
            ? "border-primary bg-primary/10 text-foreground"
            : "border-border text-muted-foreground hover:border-foreground hover:text-foreground",
        )}
      >
        <Icon className={cn("h-4 w-4", selected && "fill-current text-primary")} strokeWidth={1.75} />
        {t(value === "up" ? "voteUp" : "voteDown")}
      </button>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent
        // Focus the panel, not the first vote button: an auto-focused
        // "Useful" reads as a preselected answer
        onOpenAutoFocus={(e) => { e.preventDefault(); (e.currentTarget as HTMLElement).focus(); }}
        className={cn(
          "sm:max-w-md gap-0 p-6 max-h-[88dvh] overflow-y-auto outline-none",
          // Below 640px: bottom sheet, a centred modal jumps when the keyboard opens
          "max-sm:!top-auto max-sm:!bottom-0 max-sm:!left-0 max-sm:!right-0",
          "max-sm:!translate-x-0 max-sm:!translate-y-0 max-sm:!max-w-full",
          "max-sm:!rounded-b-none max-sm:rounded-t-lg max-sm:border-x-0 max-sm:border-b-0",
          "max-sm:data-[state=open]:!slide-in-from-bottom-6 max-sm:data-[state=open]:!zoom-in-100",
          "max-sm:pb-[calc(1.5rem+env(safe-area-inset-bottom))]",
        )}
      >
        <DialogHeader className="mb-4 pr-6">
          <DialogTitle className="[font-family:var(--font-display)] text-xl font-medium tracking-tight text-left">
            {t("title")}
          </DialogTitle>
          <DialogDescription className="sr-only">{t("srDescription")}</DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-2">
          {voteButton("up")}
          {voteButton("down")}
        </div>

        {vote === "down" && (
          <fieldset className="mt-5 animate-in fade-in slide-in-from-top-1 duration-200">
            <legend className="text-[13px] text-foreground mb-2">{t("reasonsLabel")}</legend>
            <div className="flex flex-wrap gap-2">
              {REASONS.map((r) => {
                const on = reasons.includes(r);
                return (
                  <button
                    key={r}
                    type="button"
                    onClick={() => toggleReason(r)}
                    aria-pressed={on}
                    className={cn(
                      "px-3 py-1.5 border text-[13px] transition-colors cursor-pointer",
                      on
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border text-muted-foreground hover:border-foreground hover:text-foreground",
                    )}
                  >
                    {t(`reason_${r}`)}
                  </button>
                );
              })}
            </div>
          </fieldset>
        )}

        {vote && (
          <div className="mt-5 grid gap-2 animate-in fade-in duration-200">
            <label htmlFor={`${ids}-comment`} className="text-[13px] text-foreground">
              {t("commentLabel")}
            </label>
            <textarea
              id={`${ids}-comment`}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              maxLength={1000}
              rows={2}
              placeholder={t(vote === "down" ? "commentPlaceholderDown" : "commentPlaceholderUp")}
              className="w-full bg-transparent border border-border p-2.5 text-[13px] leading-5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-foreground transition-colors resize-none"
            />
          </div>
        )}

        {showNewsletter && (
          <div className="mt-6 pt-5 border-t border-border grid gap-3">
            <div>
              <h3 className="text-sm font-medium text-foreground">{t("newsletterTitle")}</h3>
              <p className="mt-1 text-[13px] leading-5 text-muted-foreground">{t("newsletterBody")}</p>
            </div>
            <div className="grid gap-2">
              <label htmlFor={`${ids}-email`} className="text-[13px] text-foreground">
                {t("emailLabel")}
              </label>
              <input
                id={`${ids}-email`}
                type="email"
                inputMode="email"
                autoComplete="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError(null); }}
                maxLength={254}
                placeholder={t("emailPlaceholder")}
                className="h-10 w-full bg-transparent border border-border px-2.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-foreground transition-colors"
              />
            </div>
            <label htmlFor={`${ids}-consent`} className="flex items-start gap-2.5 text-[12px] leading-5 text-muted-foreground cursor-pointer">
              <input
                id={`${ids}-consent`}
                type="checkbox"
                checked={consent}
                onChange={(e) => { setConsent(e.target.checked); setError(null); }}
                className="mt-[3px] h-3.5 w-3.5 shrink-0 accent-[var(--primary)] cursor-pointer"
              />
              <span>
                {t.rich("consent", {
                  link: (chunks) => (
                    <a
                      href="/privacy#newsletter"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline underline-offset-2 text-foreground hover:text-primary"
                    >
                      {chunks}
                    </a>
                  ),
                })}
              </span>
            </label>
          </div>
        )}

        {error && (
          <p role="alert" className="mt-3 text-[13px] text-destructive">{error}</p>
        )}

        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className={cn(
            "mt-5 w-full py-3 sm:py-2.5 text-sm font-medium tracking-wide transition-colors",
            canSubmit
              ? "bg-primary text-primary-foreground hover:bg-foreground cursor-pointer active:scale-[0.99]"
              : "bg-muted text-muted-foreground cursor-not-allowed",
          )}
        >
          {sending ? t("sending") : t("submit")}
        </button>

        <p className="mt-3 text-[11px] leading-4 text-muted-foreground">{t("anonNote")}</p>
      </DialogContent>
    </Dialog>
  );
}
