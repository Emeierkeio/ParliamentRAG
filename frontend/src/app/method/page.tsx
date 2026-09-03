"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { ArrowLeft, ExternalLink } from "lucide-react";

// Mirror di backend/config/default.yaml → authority.weights.
// Se i pesi cambiano lato backend vanno aggiornati anche qui.
const WEIGHTS = [
  { name: "wInterventions", desc: "dInterventions", weight: 0.25 },
  { name: "wCommittee", desc: "dCommittee", weight: 0.25 },
  { name: "wActs", desc: "dActs", weight: 0.2 },
  { name: "wProfession", desc: "dProfession", weight: 0.15 },
  { name: "wEducation", desc: "dEducation", weight: 0.1 },
  { name: "wRole", desc: "dRole", weight: 0.05 },
] as const;

const PAPER_LINKS = [
  { label: "linkPaper", href: "https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" },
  { label: "linkArxiv", href: "https://arxiv.org/abs/2608.13410" },
  { label: "linkOrkg", href: "https://orkg.org/papers/R1909763" },
] as const;

export default function MethodPage() {
  const t = useTranslations("Method");

  return (
    <div className="min-h-screen bg-background">
      <header className="px-6 py-5 border-b border-border">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/logo-blue.svg" alt="" width={26} height={18} />
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
            {t("tagline")}
          </p>

          <div className="mt-8 border-l-2 border-primary/40 bg-primary/[0.04] px-5 py-4">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
              {t("introTitle")}
            </p>
            <p className="text-sm leading-relaxed text-foreground/85">{t("intro")}</p>
          </div>

          <div className="mt-10 space-y-10">
            {/* 01 — Pipeline */}
            <section>
              <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                <span className="text-primary/40 text-sm tabular-nums">01</span>
                {t("pipelineTitle")}
              </h2>
              <div className="mt-2 space-y-2 pl-8">
                <p className="text-sm leading-relaxed text-muted-foreground">{t("pipelineP1")}</p>
                <p className="text-sm leading-relaxed text-muted-foreground">{t("pipelineP2")}</p>
              </div>
            </section>

            {/* 02 — Authority */}
            <section>
              <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                <span className="text-primary/40 text-sm tabular-nums">02</span>
                {t("authorityTitle")}
              </h2>
              <div className="mt-2 space-y-4 pl-8">
                <p className="text-sm leading-relaxed text-muted-foreground">{t("authorityP1")}</p>

                <div className="rounded-lg border border-border/60 overflow-hidden">
                  <div className="grid grid-cols-[1fr_auto] gap-4 px-4 py-2 bg-muted/40 text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
                    <span>{t("thComponent")}</span>
                    <span className="text-right">{t("thWeight")}</span>
                  </div>
                  <div className="divide-y divide-border/50">
                    {WEIGHTS.map((w) => (
                      <div key={w.name} className="grid grid-cols-[1fr_auto] gap-4 items-center px-4 py-2.5">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-foreground">{t(w.name)}</p>
                          <p className="text-xs text-muted-foreground">{t(w.desc)}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="hidden sm:block w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className="h-full bg-primary/70 rounded-full"
                              style={{ width: `${w.weight * 100 * 2.5}%` }}
                            />
                          </div>
                          <span className="text-sm font-semibold tabular-nums text-foreground min-w-[2.6rem] text-right">
                            {Math.round(w.weight * 100)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <p className="text-sm leading-relaxed text-muted-foreground">
                  {t.rich("authorityP2", {
                    ranking: (chunks) => (
                      <Link href="/ranking" className="text-primary underline underline-offset-2 hover:text-primary/80">
                        {chunks}
                      </Link>
                    ),
                  })}
                </p>
              </div>
            </section>

            {/* 03 — Citations */}
            <section>
              <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                <span className="text-primary/40 text-sm tabular-nums">03</span>
                {t("citationsTitle")}
              </h2>
              <div className="mt-2 space-y-2 pl-8">
                <p className="text-sm leading-relaxed text-muted-foreground">{t("citationsP1")}</p>
                <p className="text-sm leading-relaxed text-muted-foreground">{t("citationsP2")}</p>
              </div>
            </section>

            {/* 04 — Limits */}
            <section>
              <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                <span className="text-primary/40 text-sm tabular-nums">04</span>
                {t("limitsTitle")}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground pl-8">{t("limitsP1")}</p>
            </section>

            {/* 05 — Compass */}
            <section>
              <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                <span className="text-primary/40 text-sm tabular-nums">05</span>
                {t("compassTitle")}
              </h2>
              <div className="mt-2 space-y-2 pl-8">
                <p className="text-sm leading-relaxed text-muted-foreground">{t("compassP1")}</p>
                <p className="text-sm leading-relaxed text-muted-foreground">{t("compassP2")}</p>
              </div>
            </section>

            {/* 06 — Paper */}
            <section>
              <h2 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight flex items-baseline gap-3">
                <span className="text-primary/40 text-sm tabular-nums">06</span>
                {t("linksTitle")}
              </h2>
              <div className="mt-2 pl-8">
                <p className="text-sm leading-relaxed text-muted-foreground">{t("linksIntro")}</p>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                  {PAPER_LINKS.map((l) => (
                    <a
                      key={l.href}
                      href={l.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm text-foreground/80 border-b border-border pb-0.5 hover:border-primary hover:text-primary transition-colors"
                    >
                      {t(l.label)}
                      <ExternalLink className="h-3 w-3 text-muted-foreground/60" />
                    </a>
                  ))}
                </div>
              </div>
            </section>
          </div>
        </article>
      </main>
    </div>
  );
}
