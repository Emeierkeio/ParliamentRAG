"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Sidebar } from "@/components/layout";
import { useSidebar } from "@/hooks";

const PAPER_URL = "/who-speaks-matters-iswc2026.pdf";
const GITHUB_URL = "https://github.com/Emeierkeio/ParliamentRAG";

const STEPS = [1, 2, 3, 4, 5, 6, 7, 8] as const;

// Mirror of backend/config/default.yaml → authority.weights.
// If the weights change on the backend they must be updated here too.
const WEIGHTS = [
  { name: "wInterventions", desc: "dInterventions", weight: 0.25 },
  { name: "wCommittee", desc: "dCommittee", weight: 0.25 },
  { name: "wActs", desc: "dActs", weight: 0.2 },
  { name: "wProfession", desc: "dProfession", weight: 0.15 },
  { name: "wEducation", desc: "dEducation", weight: 0.1 },
  { name: "wRole", desc: "dRole", weight: 0.05 },
] as const;

function SectionTitle({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="[font-family:var(--font-display)] text-2xl font-semibold tracking-tight scroll-mt-6"
    >
      {children}
    </h2>
  );
}

function Body({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-3 text-muted-foreground leading-relaxed max-w-[65ch]">{children}</p>
  );
}

export default function MetodologiaPage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const tm = useTranslations("Methodology");
  const tmd = useTranslations("Method");
  const tl = useTranslations("Landing");

  return (
    <div className="flex h-dvh overflow-hidden bg-background pb-[calc(4.75rem+env(safe-area-inset-bottom))] md:pb-0">
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={toggle}
        isMobile={isMobile}
        isMobileOpen={isMobileOpen}
        onCloseMobile={closeMobile}
      />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
          <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-semibold tracking-tight">
            {tm("pageTitle")}
          </h1>
          <p className="mt-4 [font-family:var(--font-display)] text-lg text-muted-foreground">
            {tm("intro")}
          </p>
          <p className="mt-5 text-muted-foreground leading-relaxed max-w-[65ch] border-l-2 border-l-foreground/70 pl-3">
            {tmd("intro")}
          </p>

          <section className="mt-12">
            <SectionTitle id="pipeline">{tm("howItWorks")}</SectionTitle>
            <Body>{tl("iterIntro")}</Body>

            <ol className="mt-8">
              {STEPS.map((n) => {
                const last = n === STEPS.length;
                return (
                  <li key={n} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <span
                        aria-hidden
                        className={
                          last
                            ? "mt-1.5 h-2.5 w-2.5 shrink-0 bg-foreground"
                            : "mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-foreground"
                        }
                      />
                      {!last && (
                        <span aria-hidden className="flex-1 border-l border-border" />
                      )}
                    </div>
                    <div className={last ? "" : "pb-8"}>
                      <h3 className="font-semibold">{tl(`iter${n}Title`)}</h3>
                      <p className="mt-1 text-sm text-muted-foreground leading-relaxed max-w-[65ch]">
                        {tl(`iter${n}Desc`)}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
            <Body>{tmd("pipelineP2")}</Body>
          </section>

          <section className="mt-12">
            <SectionTitle id="autorevolezza">{tm("authTitle")}</SectionTitle>
            <Body>{tmd("authorityP1")}</Body>

            <div className="mt-5 border border-border max-w-[65ch]">
              <div className="grid grid-cols-[1fr_auto] gap-4 px-4 py-2 bg-muted/40 text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
                <span>{tmd("thComponent")}</span>
                <span className="text-right">{tmd("thWeight")}</span>
              </div>
              <div className="divide-y divide-border">
                {WEIGHTS.map((w) => (
                  <div
                    key={w.name}
                    className="grid grid-cols-[1fr_auto] gap-4 items-center px-4 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground">{tmd(w.name)}</p>
                      <p className="text-xs text-muted-foreground">{tmd(w.desc)}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="hidden sm:block w-24 h-1.5 bg-muted overflow-hidden">
                        <div
                          className="h-full bg-primary/70"
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

            <Body>
              {tmd.rich("authorityP2", {
                ranking: (chunks) => (
                  <Link
                    href="/ranking"
                    className="text-foreground underline underline-offset-2 decoration-border hover:decoration-foreground"
                  >
                    {chunks}
                  </Link>
                ),
              })}
            </Body>
          </section>

          <section className="mt-12">
            <SectionTitle id="citazioni">{tmd("citationsTitle")}</SectionTitle>
            <Body>{tmd("citationsP1")}</Body>
            <Body>{tmd("citationsP2")}</Body>
          </section>

          <section className="mt-12">
            <SectionTitle id="bussola">{tmd("compassTitle")}</SectionTitle>
            <Body>{tmd("compassP1")}</Body>
            <Body>{tmd("compassP2")}</Body>
          </section>

          <section className="mt-12">
            <SectionTitle id="grafo">{tm("kgTitle")}</SectionTitle>
            <Body>{tm("kgBody")}</Body>
          </section>

          <section className="mt-12">
            <SectionTitle id="valutazione">{tm("evalTitle")}</SectionTitle>
            <Body>{tm("evalBody")}</Body>
            <p className="mt-3 font-mono text-sm leading-relaxed max-w-[65ch]">
              {tm("evalResults")}
            </p>
          </section>

          <section className="mt-12">
            <SectionTitle id="limiti">{tmd("limitsTitle")}</SectionTitle>
            <Body>{tmd("limitsP1")}</Body>
          </section>

          <section className="mt-14">
            <SectionTitle>{tm("technicalTitle")}</SectionTitle>
            <Body>{tm("technicalBody")}</Body>
            <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-2 border-t pt-4">
              <a
                href={PAPER_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                {tm("paperCta")}
              </a>
              <a
                href="https://arxiv.org/abs/2608.13410"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                arXiv
              </a>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                {tm("githubCta")}
              </a>
              <Link
                href="/data"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                {tm("dataCta")}
              </Link>
              <a
                href="https://orkg.org/papers/R1909763"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                {tm("orkgCta")}
              </a>
              <a
                href="https://doi.org/10.5281/zenodo.21560331"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                {tm("zenodoCta")}
              </a>
              <a
                href="https://mcp.parliamentrag.it"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors border-b border-border hover:border-foreground pb-0.5"
              >
                {tm("mcpCta")}
              </a>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
