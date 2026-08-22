"use client";

// Booth survey per ISWC 2026 (issue #21): raggiunta via QR al banchetto
// della demo. Mobile-first, una schermata, quattro affermazioni su scala
// 1-5, ruolo opzionale, commento libero.

import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { config } from "@/config";
import { cn } from "@/lib/utils";

const QUESTION_KEYS = ["q1", "q2", "q3", "q4"] as const;
const ROLE_KEYS = ["researcher", "journalist", "student", "citizen", "other"] as const;

type Answers = Partial<Record<(typeof QUESTION_KEYS)[number], number>>;

export default function IswcBoothPage() {
  const t = useTranslations("Booth");
  const locale = useLocale();
  const [answers, setAnswers] = useState<Answers>({});
  const [role, setRole] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const complete = QUESTION_KEYS.every((k) => answers[k] !== undefined);

  const submit = useCallback(async () => {
    if (!complete || sending) return;
    setSending(true);
    try {
      await fetch(`${config.api.baseUrl}/feedback/booth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          q1: answers.q1, q2: answers.q2, q3: answers.q3, q4: answers.q4,
          comment: comment.trim() || null,
          role,
          locale,
        }),
      });
      setSubmitted(true);
    } catch {
      // rete del centro congressi: si ringrazia comunque, il banchetto
      // raccoglie il resto a voce
      setSubmitted(true);
    }
  }, [answers, comment, role, locale, complete, sending]);

  if (submitted) {
    return (
      <main className="min-h-dvh bg-background flex items-center justify-center px-6">
        <div className="max-w-sm text-center space-y-4">
          <Check className="h-8 w-8 mx-auto text-primary" strokeWidth={1.5} />
          <h1 className="[font-family:var(--font-display)] text-2xl font-medium tracking-tight">
            {t("thanksTitle")}
          </h1>
          <p className="text-[15px] leading-7 text-muted-foreground">{t("thanksBody")}</p>
          <Link
            href="/home"
            className="group inline-flex items-center gap-1.5 border-b border-border pb-1 text-sm text-foreground/80 hover:border-primary hover:text-primary transition-colors"
          >
            {t("tryCta")}
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-dvh bg-background">
      <div className="max-w-md mx-auto px-6 py-10">
        <header className="mb-8">
          <Image src="/logo-blue.svg" alt="ParliamentRAG" width={34} height={24} className="mb-5 dark:invert" />
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
            ISWC 2026 · Bari
          </p>
          <h1 className="[font-family:var(--font-display)] text-3xl font-medium tracking-tight leading-tight">
            {t("title")}
          </h1>
          <p className="mt-3 text-[15px] leading-7 text-muted-foreground">{t("intro")}</p>
        </header>

        <div className="space-y-7">
          {QUESTION_KEYS.map((key, i) => (
            <fieldset key={key}>
              <legend className="text-[15px] leading-6 text-foreground mb-3">
                <span className="[font-family:var(--font-display)] text-muted-foreground mr-2">{i + 1}.</span>
                {t(key)}
              </legend>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-muted-foreground w-16">{t("scaleLow")}</span>
                <div className="flex gap-1.5 flex-1 justify-center">
                  {[1, 2, 3, 4, 5].map((v) => (
                    <button
                      key={v}
                      onClick={() => setAnswers((a) => ({ ...a, [key]: v }))}
                      aria-label={`${v}/5`}
                      className={cn(
                        "h-9 w-9 border text-sm tabular-nums transition-colors cursor-pointer",
                        answers[key] === v
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border text-muted-foreground hover:border-foreground hover:text-foreground",
                      )}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                <span className="text-[11px] text-muted-foreground w-16 text-right">{t("scaleHigh")}</span>
              </div>
            </fieldset>
          ))}

          <fieldset>
            <legend className="text-[13px] text-muted-foreground mb-3">{t("roleLabel")}</legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2.5">
              {ROLE_KEYS.map((r) => (
                <button
                  key={r}
                  onClick={() => setRole(role === r ? null : r)}
                  className={cn(
                    "border-b pb-0.5 text-sm transition-colors cursor-pointer",
                    role === r
                      ? "border-primary text-primary"
                      : "border-border text-foreground/70 hover:border-foreground hover:text-foreground",
                  )}
                >
                  {t(`role_${r}`)}
                </button>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor="booth-comment" className="text-[13px] text-muted-foreground block mb-2">
              {t("commentLabel")}
            </label>
            <textarea
              id="booth-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              maxLength={1000}
              rows={3}
              placeholder={t("commentPlaceholder")}
              className="w-full bg-transparent border border-border p-3 text-[15px] leading-6 text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-foreground transition-colors resize-none"
            />
          </div>

          <button
            onClick={submit}
            disabled={!complete || sending}
            className={cn(
              "w-full py-3.5 text-[15px] font-medium tracking-wide transition-colors",
              complete
                ? "bg-primary text-primary-foreground hover:bg-foreground cursor-pointer"
                : "bg-muted text-muted-foreground cursor-not-allowed",
            )}
          >
            {complete ? t("submit") : t("submitIncomplete")}
          </button>
        </div>
      </div>
    </main>
  );
}
