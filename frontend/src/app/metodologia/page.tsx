"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Sidebar } from "@/components/layout";
import { useSidebar } from "@/hooks";

const PAPER_URL = "/who-speaks-matters-iswc2026.pdf";
const GITHUB_URL = "https://github.com/Emeierkeio/ParliamentRAG";

const STEPS = [1, 2, 3, 4, 5, 6, 7, 8] as const;

export default function MetodologiaPage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const tm = useTranslations("Methodology");
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

          <section className="mt-12">
            <h2 className="[font-family:var(--font-display)] text-2xl font-semibold tracking-tight">
              {tm("howItWorks")}
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed max-w-[65ch]">
              {tl("iterIntro")}
            </p>

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
          </section>

          <section className="mt-14">
            <h2 className="[font-family:var(--font-display)] text-2xl font-semibold tracking-tight">
              {tm("technicalTitle")}
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed max-w-[65ch]">
              {tm("technicalBody")}
            </p>
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
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
