"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";

const SECTIONS = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"] as const;

export default function PrivacyPage() {
  const t = useTranslations("Privacy");

  return (
    <div className="min-h-screen bg-background">
      <header className="px-6 py-5 border-b border-border">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/logo-blue.svg" alt="" width={27} height={15} />
            <span className="[font-family:var(--font-display)] text-sm font-medium text-foreground">
              ParliamentRAG
            </span>
          </Link>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t("backHome")}
          </Link>
        </div>
      </header>

      <main className="px-6 py-14">
        <article className="max-w-3xl mx-auto">
          <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-medium tracking-tight">
            {t("title")}
          </h1>
          <p className="mt-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
            {t("updated")}
          </p>

          <div className="mt-8 border-l-2 border-primary/40 bg-primary/[0.04] px-5 py-4">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
              {t("introTitle")}
            </p>
            <p className="text-sm leading-relaxed text-foreground/85">{t("intro")}</p>
          </div>

          <div className="mt-10 space-y-8">
            {SECTIONS.map((s, i) => (
              <section key={s}>
                <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                  <span className="text-primary/40 text-sm tabular-nums">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {t(`${s}t`)}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground pl-8">
                  {t(`${s}b`)}
                </p>
              </section>
            ))}
          </div>
        </article>
      </main>
    </div>
  );
}
