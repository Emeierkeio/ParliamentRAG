"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";

// Landing page of the Brevo double opt-in link (redirectionUrl).

const NEXT = [
  { key: "deputies", href: "/parlamentari" },
  { key: "groups", href: "/gruppi" },
  { key: "method", href: "/method" },
] as const;

export default function NewsletterConfirmedPage() {
  const t = useTranslations("NewsletterConfirmed");

  return (
    <div className="min-h-[100dvh] flex flex-col bg-background">
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

      <main className="flex-1 px-6 pt-16 pb-20 md:pt-24">
        <div className="max-w-3xl mx-auto">
          <span
            aria-hidden
            className="flex h-10 w-10 items-center justify-center bg-primary text-primary-foreground"
          >
            <Check className="h-5 w-5" strokeWidth={2} />
          </span>

          <h1 className="mt-8 [font-family:var(--font-display)] text-4xl md:text-5xl font-medium tracking-tight leading-[1.1] text-foreground">
            {t("title")}
          </h1>
          <p className="mt-5 max-w-[52ch] text-base leading-relaxed text-muted-foreground">
            {t("body")}
          </p>

          <Link
            href="/home"
            className="group mt-10 inline-flex items-center gap-2.5 px-5 py-3 text-sm font-medium tracking-wide bg-primary text-primary-foreground hover:bg-foreground transition-colors active:scale-[0.98]"
          >
            {t("cta")}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>

          <section className="mt-20 border-t border-border pt-8">
            <h2 className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("nextTitle")}
            </h2>
            <ul className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-3 sm:gap-6">
              {NEXT.map(({ key, href }) => (
                <li key={key}>
                  <Link href={href} className="group block">
                    <span className="flex items-center justify-between gap-2 [font-family:var(--font-display)] text-lg font-medium text-foreground group-hover:text-primary transition-colors">
                      {t(`next.${key}.title`)}
                      <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                    </span>
                    <span className="mt-1.5 block text-sm leading-relaxed text-muted-foreground">
                      {t(`next.${key}.body`)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </main>
    </div>
  );
}
