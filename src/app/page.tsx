"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowRight, ArrowUpRight, FileText } from "lucide-react";
import { NewsletterSignup } from "@/components/feedback/NewsletterSignup";
import { fetchNewsletterEnabled } from "@/components/feedback/api";
import { PageDots } from "@/components/centro/PageDots";
import { SoonBadge } from "@/components/centro/SystemCard";
import { CentroPage, SectionTitle } from "@/components/centro/CentroPage";
import { SystemCard } from "@/components/centro/SystemCard";
import { PAPER_DEMO_PDF, PAPER_DEMO_TITLE, PAPER_IN_USE_PDF, PAPER_IN_USE_TITLE, SYSTEMS } from "@/components/centro/systems";
import { useKgStats } from "@/hooks/use-kg-stats";
import { SplitWords } from "@/components/motion/SplitWords";
import { PinSection, PinStep, usePinProgress } from "@/components/motion/PinSection";
import { ThemeShift } from "@/components/motion/ThemeShift";
import { PickerList } from "@/components/motion/PickerList";
import { SCENE_QUERY, useMediaQuery } from "@/components/motion/useMediaQuery";
import { motion, useTransform } from "motion/react";
import { useLastUpdate } from "@/hooks/use-last-update";

const PILLARS = ["pillar1", "pillar2", "pillar3"] as const;
const WORK = ["work1", "work2", "work3"] as const;
const CONTACT = "contatti@parliamentrag.it";
const STENOGRAFO = SYSTEMS.find((s) => s.id === "stenografo")!;
const VERIFY_PLAN = "https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/piano-verifica.md";

function useNumber() {
  const locale = useLocale();
  return (n: number, compact = false) =>
    new Intl.NumberFormat(locale, {
      useGrouping: "always",
      ...(compact ? { notation: "compact" as const, maximumFractionDigits: 1 } : {}),
    }).format(n);
}

function useNewsletterEnabled() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let alive = true;
    fetchNewsletterEnabled().then((on) => alive && setEnabled(on));
    return () => {
      alive = false;
    };
  }, []);
  return enabled;
}

/*
 * Desktop scrolls as one long page. Below md the same content becomes seven
 * snapped screens (hero, why, one per system, papers, newsletter): the parts that
 * would overfill a phone screen (stats, pillars, open data) are desktop-only.
 */
export default function HomePage() {
  const t = useTranslations("Centro");
  const newsletter = useNewsletterEnabled();
  const screens = useMemo(
    () => [
      { id: "s-intro", label: "ParliamentRAG" },
      { id: "s-perche", label: t("whyKicker") },
      ...SYSTEMS.map((s) => ({ id: `s-${s.id}`, label: s.name })),
      { id: "s-percorsi", label: t("pathsTitle") },
      { id: "s-copertura", label: t("coverTitle") },
      { id: "s-pubblicazioni", label: t("navPublications") },
      { id: "s-faq", label: t("faqTitle") },
      ...(newsletter ? [{ id: "s-newsletter", label: t("navUpdates") }] : []),
    ],
    [t, newsletter],
  );
  // Wide screens with motion allowed get the scroll-driven scenes; the server,
  // phones and reduced motion render the same content as static sections.
  const scenes = useMediaQuery(SCENE_QUERY);
  return (
    <CentroPage reveal>
      <Hero />
      <StatsStrip />
      {scenes ? <WorkScene /> : <Mission />}
      <Systems />
      <SystemScreens />
      <Paths />
      <Coverage />
      <ThemeShift>
        <Publications />
        {scenes ? <OpenDataPicker /> : <OpenData />}
        <Faq />
        {newsletter && (
          <section id="s-newsletter" className="container-page snap-screen pb-16 md:pb-24" data-reveal>
            <NewsletterSignup source="landing" />
          </section>
        )}
      </ThemeShift>
      <PageDots screens={screens} />
    </CentroPage>
  );
}

function Hero() {
  const t = useTranslations("Centro");
  return (
    <section id="s-intro" className="container-page snap-screen grid content-center gap-10 pt-10 pb-14 sm:pt-16 md:content-start lg:grid-cols-12 lg:gap-12 lg:pt-24 lg:pb-20">
      <div className="lg:col-span-7 lg:self-center">
        <p className="label-mono" data-reveal data-reveal-y="12">{t("homeKicker")}</p>
        <h1 className="serif-display mt-5 text-[clamp(2.375rem,9vw,4.25rem)] leading-[1.04] text-fg" data-reveal="words" data-reveal-delay="0.08">
          <SplitWords text={t("homeTitle")} />
        </h1>
        <p className="mt-6 max-w-[38rem] text-[17px] leading-relaxed text-fg-secondary sm:text-lg" data-reveal data-reveal-delay="0.45">
          {t("homeLead")}
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6" data-reveal data-reveal-delay="0.55">
          <a
            href={STENOGRAFO.url}
            target="_blank"
            rel="noopener"
            className="group inline-flex h-12 items-center justify-center gap-2 rounded-full bg-brand px-6 text-[15px] font-medium text-on-brand transition-colors hover:bg-brand-hover"
          >
            {t("homeCtaSystems")}
            <ArrowUpRight className="size-4" aria-hidden />
          </a>
          <Link href="/method" className="group inline-flex min-h-11 items-center justify-center gap-1.5 text-[15px] font-medium text-brand-fg">
            {t("homeCtaMethod")}
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>
      </div>

      <aside className="hidden md:block lg:col-span-5 lg:pt-3" data-reveal data-reveal-delay="0.65" data-reveal-y="28" data-reveal-blur="10" aria-labelledby="pillars-title">
        <div className="rounded-lg border border-line bg-surface">
          <h2 id="pillars-title" className="serif-display border-b border-line px-5 py-3.5 text-[1.3125rem] leading-snug text-fg sm:px-6">
            {t("pillarsLabel")}
          </h2>
          <ol className="divide-y divide-line">
            {PILLARS.map((p, i) => (
              <li key={p} className="flex gap-4 px-5 py-4 sm:px-6">
                <span className="tabular font-mono text-caption leading-6 text-fg-muted">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <p className="font-semibold leading-6 text-fg">{t(`${p}Title`)}</p>
                  <p className="mt-1 text-[15px] leading-relaxed text-fg-secondary">{t(`${p}Body`)}</p>
                  <p className="mt-2 border-l-2 border-brand pl-3 text-sm leading-relaxed text-fg-secondary">
                    <span className="font-medium text-brand-fg">{t("pillarsHow")}.</span> {t(`${p}How`)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
          <Link href="/method" className="group flex items-center gap-2 border-t border-line px-5 py-3 text-[15px] font-medium text-brand-fg sm:px-6">
            {t("pillarsMore")}
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>
      </aside>
    </section>
  );
}

function StatsStrip() {
  const t = useTranslations("Centro");
  const tl = useTranslations("Landing");
  const locale = useLocale();
  const kg = useKgStats();
  const iso = useLastUpdate();
  const fmt = useNumber();
  const date = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long", year: "numeric" }).format(new Date(`${iso}T12:00:00`));
  const items = [
    { value: fmt(kg.sessions), label: tl("statsSessions") },
    { value: fmt(kg.speeches), label: tl("statsSpeeches") },
    { value: fmt(kg.individual_votes, true), label: tl("statsVotes") },
  ];
  return (
    <div className="hidden border-y border-line bg-surface md:block">
      <div className="container-page flex flex-wrap items-baseline gap-x-8 gap-y-2 py-5 text-[15px]" data-reveal="group" data-reveal-delay="0.8">
        <p className="label-mono w-full sm:w-auto" data-reveal-item>{t("statsLabel")}</p>
        {items.map((it) => (
          <p key={it.label} data-reveal-item>
            <span className="tabular font-semibold text-fg">{it.value}</span> <span className="text-fg-secondary">{it.label}</span>
          </p>
        ))}
        <p className="text-sm text-fg-muted sm:ml-auto" data-reveal-item>{tl("statsAsOf", { date })}</p>
      </div>
    </div>
  );
}

/** Why the centre exists and its three lines of work: method, data, verification. */
function Mission() {
  const t = useTranslations("Centro");
  return (
    <section
      id="s-perche"
      className="container-page snap-screen grid content-center gap-10 py-14 md:content-start md:py-24 lg:grid-cols-12 lg:gap-12"
      aria-labelledby="perche-title"
    >
      <div className="lg:col-span-6" data-reveal>
        <p className="label-mono">{t("whyKicker")}</p>
        <h2 id="perche-title" className="serif-display mt-4 text-[clamp(1.75rem,5vw,2.5rem)] leading-[1.12] text-fg">
          {t("whyTitle")}
        </h2>
        <p className="mt-5 text-base leading-relaxed text-fg-secondary sm:text-[17px]">{t("whyBody1")}</p>
        <p className="mt-4 hidden text-base leading-relaxed text-fg-secondary sm:block sm:text-[17px]">{t("whyBody2")}</p>
      </div>
      <div className="lg:col-span-6">
        <p className="label-mono">{t("workKicker")}</p>
        <ol className="mt-4 divide-y divide-line border-y border-line" data-reveal="group" data-reveal-delay="0.1">
          {WORK.map((w, i) => (
            <li key={w} className="flex gap-4 py-4 sm:py-5" data-reveal-item>
              <span className="tabular font-mono text-caption leading-6 text-fg-muted">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <p className="font-semibold leading-6 text-fg">{t(`${w}Title`)}</p>
                <p className="mt-1 hidden text-[15px] leading-relaxed text-fg-secondary sm:block">{t(`${w}Body`)}</p>
              </div>
            </li>
          ))}
        </ol>
        <a
          href={VERIFY_PLAN}
          target="_blank"
          rel="noopener noreferrer"
          className="group mt-5 inline-flex min-h-11 items-center gap-1.5 text-[15px] font-medium text-brand-fg"
        >
          {t("workLink")}
          <ArrowUpRight className="size-4" aria-hidden />
        </a>
      </div>
    </section>
  );
}

function Systems() {
  const t = useTranslations("Centro");
  return (
    <section className="container-page hidden py-16 md:block md:py-24" aria-labelledby="sistemi-title">
      <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between" data-reveal data-reveal-amount="0.3">
        <SectionTitle id="sistemi-title" title={t("systemsTitle")} lead={t("systemsLead")} />
        <Link href="/sistemi" className="group inline-flex min-h-11 shrink-0 items-center gap-1.5 text-[15px] font-medium text-brand-fg">
          {t("systemsMore")}
          <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      </div>
      <ul className="mt-10 grid gap-4 md:grid-cols-3 md:gap-5" data-reveal="group" data-reveal-delay="0.1" data-reveal-y="28">
        {SYSTEMS.map((s) => (
          <li key={s.id} className="flex" data-reveal-item>
            <SystemCard system={s} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Phone-only: one screen per system, with a single action each. */
function SystemScreens() {
  const t = useTranslations("Centro");
  return (
    <div className="md:hidden">
      {SYSTEMS.map((s, i) => {
        const { Mark } = s;
        const action = "mt-8 inline-flex h-12 w-full items-center justify-center gap-2 rounded-full text-[15px] font-medium";
        return (
          <section key={s.id} id={`s-${s.id}`} className="snap-screen border-t border-line" aria-labelledby={`s-${s.id}-name`}>
            <div data-reveal data-reveal-amount="0.3">
            <p className="label-mono">{t("systemOf", { n: i + 1, total: SYSTEMS.length })}</p>
            <div className="mt-8 flex items-center justify-between gap-4">
              <Mark size={64} />
              {!s.live && <SoonBadge />}
            </div>
            <h2 id={`s-${s.id}-name`} className="serif-display mt-6 text-[2.5rem] leading-none text-fg">
              {s.name}
            </h2>
            <p className="mt-4 text-[17px] leading-relaxed text-fg-secondary">{t(`${s.id}Job`)}</p>
            <p className="mt-3 font-mono text-sm text-fg-muted">{s.domain}</p>
            {s.live ? (
              <a href={s.url} target="_blank" rel="noopener" className={`${action} bg-brand text-on-brand`}>
                {t("visitDomain", { domain: s.domain })}
                <ArrowUpRight className="size-4" aria-hidden />
              </a>
            ) : (
              <Link href={`/sistemi#${s.id}`} className={`${action} border border-line-strong bg-surface text-fg`}>
                {t("readMore")}
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            )}
            </div>
          </section>
        );
      })}
    </div>
  );
}

/** One way in per audience, each with a single action. */
function Paths() {
  const t = useTranslations("Centro");
  const paths = [
    { n: 1, href: STENOGRAFO.url, external: true },
    { n: 2, href: "/pubblicazioni", external: false },
    { n: 3, href: "/sviluppatori", external: false },
  ];
  return (
    <section id="s-percorsi" className="snap-screen md:container-page md:py-24" aria-labelledby="percorsi-title">
      <h2 id="percorsi-title" className="serif-display text-[clamp(1.75rem,5vw,2.5rem)] leading-[1.12] text-fg" data-reveal data-reveal-amount="0.3">
        {t("pathsTitle")}
      </h2>
      <ul className="mt-6 grid divide-y divide-line border-y border-line md:mt-10 md:grid-cols-3 md:divide-x md:divide-y-0" data-reveal="group" data-reveal-delay="0.1">
        {paths.map(({ n, href, external }) => {
          const cta = (
            <>
              {t(`path${n}Cta`)}
              {external ? <ArrowUpRight className="size-4" aria-hidden /> : <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />}
            </>
          );
          const cls = "group mt-auto inline-flex min-h-11 items-center gap-1.5 pt-3 text-[15px] font-medium text-brand-fg";
          return (
            <li key={n} className="flex flex-col py-4 md:px-6 md:py-6 md:first:pl-0 md:last:pr-0" data-reveal-item>
              <p className="font-semibold leading-6 text-fg">{t(`path${n}Who`)}</p>
              <p className="mt-1 text-[15px] leading-relaxed text-fg-secondary">{t(`path${n}Body`)}</p>
              {external ? (
                <a href={href} target="_blank" rel="noopener" className={cls}>
                  {cta}
                </a>
              ) : (
                <Link href={href} className={cls}>
                  {cta}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** What the data covers and what it does not, and where to report a mistake. */
function Coverage() {
  const t = useTranslations("Centro");
  const yes = [1, 2, 3, 4].map((n) => t(`coverYes${n}`));
  const no = [1, 2, 3, 4].map((n) => t(`coverNo${n}`));
  return (
    <section id="s-copertura" className="snap-screen md:container-page md:py-24" aria-labelledby="copertura-title">
      <div data-reveal data-reveal-amount="0.3">
        <SectionTitle id="copertura-title" title={t("coverTitle")} lead={t("coverLead")} />
      </div>
      <div className="mt-6 grid gap-6 md:mt-10 md:grid-cols-12 md:gap-12" data-reveal="group" data-reveal-delay="0.1">
        {[
          { title: t("coverYesTitle"), items: yes, mark: "+" },
          { title: t("coverNoTitle"), items: no, mark: "–" },
        ].map((col) => (
          <div key={col.title} className="md:col-span-4" data-reveal-item>
            <p className="label-mono">{col.title}</p>
            <ul className="mt-3 space-y-2 text-[15px] leading-relaxed text-fg-secondary">
              {col.items.map((it) => (
                <li key={it} className="flex gap-3">
                  <span aria-hidden className="font-mono text-fg-muted">
                    {col.mark}
                  </span>
                  {it}
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="rounded-lg border border-line bg-surface p-5 md:col-span-4 md:p-6" data-reveal-item>
          <p className="font-semibold text-fg">{t("coverErrTitle")}</p>
          <p className="mt-2 text-[15px] leading-relaxed text-fg-secondary">
            {t.rich("coverErrBody", {
              address: CONTACT,
              email: (chunks) => (
                <a href={`mailto:${CONTACT}`} className="link">
                  {chunks}
                </a>
              ),
            })}
          </p>
        </div>
      </div>
    </section>
  );
}

/** The objections people actually raise, answered in the open. */
function Faq() {
  const t = useTranslations("Centro");
  const items = t.raw("faq") as { q: string; a: string }[];
  return (
    <section id="s-faq" className="snap-screen md:container-page md:py-24" aria-labelledby="faq-title">
      <div className="grid gap-8 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-4" data-reveal data-reveal-amount="0.3">
          <h2 id="faq-title" className="serif-display text-[clamp(1.75rem,5vw,2.5rem)] leading-[1.12] text-fg">
            {t("faqTitle")}
          </h2>
          <Link href="/privacy" className="group mt-4 inline-flex min-h-11 items-center gap-1.5 text-[15px] font-medium text-brand-fg">
            {t("faqPrivacy")}
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>
        <div className="divide-y divide-line border-y border-line lg:col-span-8" data-reveal="group" data-reveal-delay="0.1">
          {items.map((it) => (
            <details key={it.q} className="group py-1" data-reveal-item>
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-4 py-2 font-semibold text-fg [&::-webkit-details-marker]:hidden">
                {it.q}
                <span aria-hidden className="font-mono text-fg-muted transition-transform duration-300 group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="pb-4 text-[15px] leading-relaxed text-fg-secondary">{it.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

function Publications() {
  const t = useTranslations("Centro");
  const papers = [
    { href: PAPER_IN_USE_PDF, title: PAPER_IN_USE_TITLE, venue: t("pub1Venue") },
    { href: PAPER_DEMO_PDF, title: PAPER_DEMO_TITLE, venue: t("pub2Venue") },
  ];
  return (
    <section id="s-pubblicazioni" className="snap-screen" aria-labelledby="pub-title">
      <div className="grid gap-10 md:container-page md:py-24 lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-5" data-shift-reveal>
          <p className="label-mono">ISWC 2026 · Bari</p>
          <div className="mt-4">
            <SectionTitle id="pub-title" title={t("pubsTitle")} lead={t("pubsLead")} />
          </div>
          <Link
            href="/pubblicazioni"
            className="mt-8 inline-flex h-12 items-center gap-2 rounded-full bg-surface-inverse px-6 text-[15px] font-medium text-fg-inverse transition-opacity hover:opacity-90"
          >
            {t("pubsAll")}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
        <ul className="hidden gap-4 md:grid lg:col-span-7" data-reveal="group" data-reveal-amount="0.3" data-reveal-y="28">
          {papers.map((p) => (
            <li key={p.href} data-reveal-item>
              <a
                href={p.href}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex flex-col gap-4 rounded-lg border border-line bg-surface p-6 transition-colors hover:border-line-strong sm:p-7"
              >
                <p className="label-mono">{p.venue}</p>
                <p className="serif-display text-[1.375rem] leading-snug text-fg sm:text-[1.625rem]">{p.title}</p>
                <p className="text-sm text-fg-secondary">{t("authorsShort")}</p>
                <span className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-fg">
                  <FileText className="size-4" aria-hidden />
                  {t("readPdf")}
                  <ArrowUpRight className="size-3.5" aria-hidden />
                </span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function OpenData() {
  const t = useTranslations("Centro");
  const td = useTranslations("DataPage");
  const kg = useKgStats();
  const fmt = useNumber();
  const stats = [
    { value: fmt(kg.acts), label: td("stActs") },
    { value: fmt(kg.votes), label: td("stVotes") },
    { value: fmt(kg.eurovoc_concepts), label: td("stEurovoc") },
    { value: fmt(kg.triples ?? 0), label: td("stTriples") },
  ];
  return (
    <section className="container-page hidden gap-10 py-16 md:grid md:py-24 lg:grid-cols-12 lg:gap-12" aria-labelledby="dati-title">
      <div className="lg:col-span-5" data-reveal>
        <SectionTitle id="dati-title" title={t("dataTitle")} lead={t("dataLead")} />
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/data"
            className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-brand px-6 text-[15px] font-medium text-on-brand transition-colors hover:bg-brand-hover"
          >
            {t("dataCta")}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
          <Link
            href="/sviluppatori"
            className="inline-flex h-12 items-center justify-center rounded-full border border-line-strong bg-surface px-6 text-[15px] font-medium text-fg transition-colors hover:bg-surface-muted"
          >
            {t("devCta")}
          </Link>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 lg:col-span-7" data-reveal="group" data-reveal-delay="0.1">
        {stats.map((s) => (
          <div key={s.label} className="border-t border-line py-5" data-reveal-item>
            <dd className="tabular text-[clamp(1.5rem,6vw,2rem)] font-semibold tracking-[-0.02em] text-fg">{s.value}</dd>
            <dt className="mt-1 text-sm leading-snug text-fg-muted">{s.label}</dt>
          </div>
        ))}
      </dl>
    </section>
  );
}

/*
 * Wide screens: "why we exist" stays on the left while the three lines of
 * work take the right side one at a time, each led by its number scaling up
 * from an eighth, with a slight overshoot. The holds between the steps are
 * the pauses: scroll length only, the wheel is never blocked.
 */
const WORK_STEPS = [
  { enter: 0.02, exit: 0.3 },
  { enter: 0.36, exit: 0.63 },
  { enter: 0.69 },
] as const;

function WorkScene() {
  const t = useTranslations("Centro");
  return (
    <PinSection screens={4.5} aria-labelledby="perche-title">
      <div className="container-page grid h-full grid-cols-12 items-center gap-12">
        <div className="col-span-5" data-reveal data-reveal-amount="0.3">
          <p className="label-mono">{t("whyKicker")}</p>
          <h2 id="perche-title" className="serif-display mt-4 text-[clamp(2rem,3.4vw,3rem)] leading-[1.08] text-fg">
            {t("whyTitle")}
          </h2>
          <p className="mt-5 text-[17px] leading-relaxed text-fg-secondary">{t("whyBody1")}</p>
          <p className="mt-4 text-[17px] leading-relaxed text-fg-secondary">{t("whyBody2")}</p>
          <WorkRail />
        </div>
        <div className="relative col-span-7 h-[min(34rem,70svh)]">
          <p className="label-mono absolute top-0 left-0">{t("workKicker")}</p>
          {WORK.map((w, i) => (
            <PinStep key={w} {...WORK_STEPS[i]} className="absolute inset-x-0 top-10 bottom-0 flex flex-col justify-center">
              <WorkNumber n={i + 1} enter={WORK_STEPS[i].enter} />
              <h3 className="serif-display mt-2 text-[clamp(2.25rem,4vw,3.5rem)] leading-none text-fg">{t(`${w}Title`)}</h3>
              <p className="mt-5 max-w-[34rem] text-lg leading-relaxed text-fg-secondary">{t(`${w}Body`)}</p>
              {i === WORK.length - 1 && (
                <a
                  href={VERIFY_PLAN}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group mt-6 inline-flex min-h-11 items-center gap-1.5 text-[15px] font-medium text-brand-fg"
                >
                  {t("workLink")}
                  <ArrowUpRight className="size-4" aria-hidden />
                </a>
              )}
            </PinStep>
          ))}
        </div>
      </div>
    </PinSection>
  );
}

function WorkNumber({ n, enter }: { n: number; enter: number }) {
  const p = usePinProgress();
  const scale = useTransform(p, [enter, enter + 0.08, enter + 0.11], [0.125, 1.06, 1]);
  return (
    <motion.span
      aria-hidden
      className="serif-display tabular block origin-bottom-left text-[clamp(7rem,13vw,11rem)] leading-[0.85] text-brand"
      style={{ scale }}
    >
      {String(n).padStart(2, "0")}
    </motion.span>
  );
}

/** Where the scene is: three ticks, the current one long and dark. */
function WorkRail() {
  const t = useTranslations("Centro");
  const p = usePinProgress();
  return (
    <ol className="mt-10 flex gap-6" aria-hidden>
      {WORK.map((w, i) => (
        <WorkTick key={w} label={t(`${w}Title`)} from={WORK_STEPS[i].enter} to={"exit" in WORK_STEPS[i] ? WORK_STEPS[i].exit : 2} progress={p} />
      ))}
    </ol>
  );
}

function WorkTick({ label, from, to, progress }: { label: string; from: number; to: number; progress: ReturnType<typeof usePinProgress> }) {
  // Switches, never scrubs: the CSS transition eases each change.
  const on = useTransform(progress, (v): number => (v >= from && v < to + 0.05 ? 1 : 0));
  const scaleX = useTransform(on, (v) => (v ? 1 : 0.4));
  const opacity = useTransform(on, (v) => (v ? 1 : 0.45));
  const ease = "transition-[transform,opacity] duration-500 ease-[cubic-bezier(.16,1,.3,1)]";
  return (
    <li className="flex flex-col gap-2">
      <motion.span className={`block h-0.5 w-10 origin-left rounded-full bg-fg ${ease}`} style={{ scaleX, opacity }} />
      <motion.span className={`label-mono ${ease}`} style={{ opacity }}>
        {label}
      </motion.span>
    </li>
  );
}

/** Wide screens: the graph counts as a picker wheel beside the download links. */
function OpenDataPicker() {
  const t = useTranslations("Centro");
  const td = useTranslations("DataPage");
  const kg = useKgStats();
  const fmt = useNumber();
  const stats = [
    { value: fmt(kg.sessions), label: td("stSessions") },
    { value: fmt(kg.speeches), label: td("stSpeeches") },
    { value: fmt(kg.people), label: td("stPeople") },
    { value: fmt(kg.acts), label: td("stActs") },
    { value: fmt(kg.votes), label: td("stVotes") },
    { value: fmt(kg.individual_votes), label: td("stIndVotes") },
    { value: fmt(kg.eurovoc_concepts), label: td("stEurovoc") },
    ...(kg.triples ? [{ value: fmt(kg.triples), label: td("stTriples") }] : []),
  ];
  return (
    <PickerList
      aria-labelledby="dati-title"
      aside={
        <div data-reveal data-reveal-amount="0.3">
          <SectionTitle id="dati-title" title={t("dataTitle")} lead={t("dataLead")} />
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/data"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-brand px-6 text-[15px] font-medium text-on-brand transition-colors hover:bg-brand-hover"
            >
              {t("dataCta")}
              <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link
              href="/sviluppatori"
              className="inline-flex h-12 items-center justify-center rounded-full border border-line-strong bg-surface px-6 text-[15px] font-medium text-fg transition-colors hover:bg-surface-muted"
            >
              {t("devCta")}
            </Link>
          </div>
        </div>
      }
      rows={stats.map((s) => (
        <p key={s.label} className="flex items-baseline gap-5">
          <span className="serif-display tabular text-[clamp(2.25rem,3.6vw,3.25rem)] leading-none text-fg">{s.value}</span>
          <span className="text-lg text-fg-secondary">{s.label}</span>
        </p>
      ))}
    />
  );
}
