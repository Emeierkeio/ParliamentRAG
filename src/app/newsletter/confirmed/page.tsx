"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";

// Landing page of the Brevo double opt-in link (redirectionUrl).

export default function NewsletterConfirmedPage() {
  const t = useTranslations("NewsletterConfirmed");

  return (
    <div className="min-h-[100dvh] bg-background">
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
        <div className="max-w-xl mx-auto">
          <h1 className="[font-family:var(--font-display)] text-3xl font-medium tracking-tight">
            {t("title")}
          </h1>
          <p className="mt-6 text-sm leading-relaxed text-muted-foreground">{t("body")}</p>
          <Link
            href="/home"
            className="mt-8 inline-block px-5 py-2.5 text-sm font-medium tracking-wide bg-primary text-primary-foreground hover:bg-foreground transition-colors active:scale-[0.99]"
          >
            {t("cta")}
          </Link>
        </div>
      </main>
    </div>
  );
}
