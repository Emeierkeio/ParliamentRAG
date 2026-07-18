"use client";

import { useState, useEffect } from "react";
import { useTranslations, useLocale } from "next-intl";
import Link from "next/link";
import Image from "next/image";
import { Fraunces } from "next/font/google";
import { ArrowRight, ArrowUpRight, Globe, Check, Award } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { LOCALES } from "@/components/layout/LanguageSelector";

/* ── Display typeface — editorial serif with optical sizing ────── */
const fraunces = Fraunces({
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

/* ── Rotating topics ───────────────────────────────────────────── */
const TOPIC_KEYS = ["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10","t11","t12"] as const;

function useSyncedRotation(length: number, intervalMs = 7000) {
  const [index, setIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => {
        setIndex((i) => (i + 1) % length);
        setIsAnimating(false);
      }, 380);
    }, intervalMs);
    return () => clearInterval(id);
  }, [length, intervalMs]);

  return { index, isAnimating };
}

/* ── Real quotes from the DB — verbatim, aligned 1:1 with ROTATING_TOPICS ── */
const QUOTES = [
  {
    text: "«[…] il PNRR rappresentava un'occasione straordinaria, forse irripetibile, per colmare finalmente il divario che ci separa dagli altri Paesi europei.»",
    who: "Valentina Grippo",
    meta: "· Azione · Camera, seduta n. 608 · 4 febbraio 2026",
  },
  {
    text: "«[…] il sistema non riesce ad intercettarli, […] le liste di attesa scoraggiano, […] la consapevolezza della patologia è ancora insufficiente, […] lo stigma sociale frena ogni richiesta di aiuto.»",
    who: "Ilenia Malavasi",
    meta: "· Partito Democratico · Camera, seduta n. 668 · 3 giugno 2026",
  },
  {
    text: "«[…] la discussione sull'atomo in Italia non è onesta, non è competente ed è soprattutto surreale. Si parla, deliberatamente, di tecnologie che addirittura non saranno in commercio se non tra più di 30, 40 anni.»",
    who: "Marco Grimaldi",
    meta: "· Alleanza Verdi e Sinistra · Camera, seduta n. 665 · 26 maggio 2026",
  },
  {
    text: "«Sono tantissimi i lavoratori il cui reddito è al di sotto della soglia di povertà, pur essendo regolarmente occupati. […] Noi pensiamo che tutto questo sia veramente inaccettabile per uno Stato civile.»",
    who: "Davide Aiello",
    meta: "· MoVimento 5 Stelle · Camera, seduta n. 15 · 29 novembre 2022",
  },
  {
    text: "«[…] oggi non è in gioco solo la sovranità del popolo ucraino, ma gli stessi fondamenti della nostra civiltà: diritto, sapere, umanesimo del lavoro, solidarietà, socialità, radici giudaico-cristiane, democrazia.»",
    who: "Fabio Rampelli",
    meta: "· Fratelli d'Italia · Camera, seduta n. 673 · 11 giugno 2026",
  },
  {
    text: "«[…] la pressione fiscale ai massimi da 11 anni. La colpa non è di Bruxelles, la colpa è del vostro Governo di centrodestra. Dovete assumervene le responsabilità.»",
    who: "Piero De Luca",
    meta: "· Partito Democratico · Camera, seduta n. 683 · 30 giugno 2026",
  },
  {
    text: "«[…] oggi il vostro Governo ha presentato una proposta di riforma dell'autonomia differenziata che va esattamente nella direzione opposta a quella da lei auspicata.»",
    who: "Maria Elena Boschi",
    meta: "· Italia Viva · Camera, seduta n. 683 · 30 giugno 2026",
  },
  {
    text: "«L'aspettavano gli avvocati, ma l'aspettavano soprattutto […] 500.000 cittadini che tutti gli anni vengono prosciolti, assolti in Italia, con fascicoli archiviati.»",
    who: "Gianluca Vinci",
    meta: "· Fratelli d'Italia · Camera, seduta n. 667 · 28 maggio 2026",
  },
  {
    text: "«[…] una strategia molto più ampia che il Governo sta portando avanti fin dall'inizio della legislatura per restituire allo Stato la capacità di governare i flussi migratori e di far rispettare le proprie regole.»",
    who: "Simona Bordonali",
    meta: "· Lega · Camera, seduta n. 676 · 16 giugno 2026",
  },
  {
    text: "«È una scelta che rischia di snaturare la funzione di un investimento finanziato con risorse pubbliche e pensato per garantire il diritto allo studio.»",
    who: "Roberto Giachetti",
    meta: "· Italia Viva · Camera, seduta n. 684 · 1 luglio 2026",
  },
  {
    text: "«Nel solo 2025 si stima che il cambiamento climatico abbia portato a 24.400 decessi in Europa a causa del caldo estremo. Di questi, ben 4.597 sono attribuiti all'Italia.»",
    who: "Patrizia Prestipino",
    meta: "· Partito Democratico · Camera, seduta n. 675 · 15 giugno 2026",
  },
  {
    text: "«Poi avete proposto il Ponte sullo Stretto, e lì veramente c'è stata la prima pietra tombale di un qualcosa che non si farà.»",
    who: "Agostino Santillo",
    meta: "· MoVimento 5 Stelle · Camera, seduta n. 681 · 23 giugno 2026",
  },
];

/* ── Data freshness line (masthead) — latest session in the DB ── */
function useEditionDate() {
  const t = useTranslations("Landing");
  const locale = useLocale();
  const [label, setLabel] = useState("");
  useEffect(() => {
    let cancelled = false;
    fetch("/api/config/last-update")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        const iso: string | undefined = data?.last_update;
        if (!iso) return;
        const formatted = new Intl.DateTimeFormat(locale, {
          day: "numeric",
          month: "long",
          year: "numeric",
        }).format(new Date(`${iso}T12:00:00`));
        setLabel(t("edition", { date: formatted }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [locale, t]);
  return label;
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function LandingPage() {
  const t = useTranslations("Landing");
  const edition = useEditionDate();
  const { index: topicIndex, isAnimating } = useSyncedRotation(
    TOPIC_KEYS.length
  );

  return (
    <div
      className={`${fraunces.variable} min-h-screen bg-background text-foreground`}
    >
      {/* ── Masthead ───────────────────────────────────────────── */}
      <header className="border-b-2 border-foreground">
        <div className="max-w-6xl mx-auto px-6">
          {/* Edition line */}
          <div className="flex items-center justify-between gap-3 py-2 text-[10px] sm:text-[11px] uppercase tracking-[0.14em] sm:tracking-[0.2em] text-muted-foreground border-b border-border">
            <span className="min-w-0">{edition || " "}</span>
            <span className="hidden sm:inline">
              {t("mastheadInstitution")}
            </span>
            <span className="inline-flex shrink-0 items-center gap-3 sm:gap-5 whitespace-nowrap">
              <span>{t("mastheadLeg")}</span>
              <LanguageMenu />
            </span>
          </div>
          {/* Wordmark row */}
          <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 py-5">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center bg-primary">
                <Image src="/logo.svg" alt="" width={26} height={26} />
              </span>
              <span className="[font-family:var(--font-display)] text-2xl sm:text-3xl font-semibold tracking-tight">
                ParliamentRAG
              </span>
            </div>
            <Link
              href="/home"
              className="group inline-flex items-baseline gap-1.5 whitespace-nowrap text-sm font-medium border-b-2 border-foreground pb-0.5 hover:border-primary hover:text-primary transition-colors cursor-pointer"
            >
              {t("accessCta")}
              <ArrowRight className="h-3.5 w-3.5 self-center transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
        {/* Accolade band — newspaper-style credential under the masthead */}
        <a
          href="https://iswc2026.semanticweb.org"
          target="_blank"
          rel="noopener noreferrer"
          className="group block border-t border-border bg-primary/[0.05] hover:bg-primary/[0.09] transition-colors cursor-pointer"
        >
          <span className="flex flex-wrap items-center justify-center gap-x-2.5 gap-y-0.5 py-2 px-4 sm:px-6 text-[11px] uppercase tracking-[0.14em] sm:tracking-[0.2em] text-center text-foreground/60 group-hover:text-foreground transition-colors">
            <Award className="h-3.5 w-3.5 text-primary shrink-0" />
            <span className="[font-family:var(--font-display)] normal-case tracking-normal text-[13px] font-semibold text-primary whitespace-nowrap">
              ISWC 2026
            </span>
            <span aria-hidden className="hidden sm:inline text-border">|</span>
            <span>{t("iswcBadge")}</span>
          </span>
        </a>
      </header>

      <SideTOC />

      {/* ── Front page ─────────────────────────────────────────── */}
      <section id="hero" className="px-6 pt-14 sm:pt-20 pb-16">
        <div className="max-w-6xl mx-auto grid lg:grid-cols-12 gap-12 lg:gap-8 items-start">
          {/* Headline column */}
          <div className="lg:col-span-7">
            <RotatingHero index={topicIndex} isAnimating={isAnimating} />

            <p className="mt-8 text-lg leading-relaxed text-muted-foreground max-w-xl">
              {t.rich("heroSub", {
                strong: (chunks) => <span className="text-foreground">{chunks}</span>,
              })}
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-4">
              <Link
                href="/home"
                className="group inline-flex w-full sm:w-auto justify-center items-center gap-3 bg-primary text-primary-foreground px-7 py-3.5 text-[15px] font-medium tracking-wide hover:bg-foreground transition-colors cursor-pointer"
              >
                {t("ctaPrimary")}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <a
                href="https://github.com/Emeierkeio/thesis-ParliamentRAG"
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-baseline gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <span className="border-b border-border group-hover:border-foreground pb-0.5 transition-colors">
                  {t("sourceCode")}
                </span>
                <ArrowUpRight className="h-3.5 w-3.5 self-center" />
              </a>
            </div>
          </div>

          {/* Column of record */}
          <aside className="lg:col-span-5 lg:pl-8 lg:border-l border-border">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
              {t("fromTranscript")}
            </p>
            {/* All quotes share one grid cell: the column reserves the height
                of the tallest quote, so rotation never shifts the layout. */}
            <div className="grid">
              {QUOTES.map((q, i) => {
                const active = i === topicIndex;
                return (
                  <figure
                    key={q.who + i}
                    aria-hidden={active ? undefined : true}
                    className={`[grid-area:1/1] [font-family:var(--font-display)] transition-opacity duration-300 ease-out motion-reduce:transition-none ${
                      active ? "" : "pointer-events-none select-none"
                    }`}
                    style={{
                      opacity: active && !isAnimating ? 1 : 0,
                      visibility: active ? "visible" : "hidden",
                    }}
                  >
                    <blockquote className="text-lg sm:text-xl leading-[1.55] text-foreground/90">
                      {q.text}
                    </blockquote>
                    <figcaption className="mt-4 text-sm not-italic font-sans">
                      <span className="font-medium text-foreground">{q.who}</span>
                      <span className="text-muted-foreground"> {q.meta}</span>
                    </figcaption>
                  </figure>
                );
              })}
            </div>
            <div className="mt-6 pt-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
              <span>{t("quoteLinkNote")}</span>
              <span className="inline-block h-2 w-2 rounded-full bg-chart-4" />
            </div>
            <p className="mt-8 text-sm leading-relaxed text-muted-foreground">
              {t("quotesExplainer")}
            </p>
          </aside>
        </div>
      </section>

      {/* ── Indice — the five instruments ──────────────────────── */}
      <section id="strumenti" className="px-6 py-14 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="I" title={t("sec1Title")} />

          <div className="mt-2">
            <IndexRow
              numeral="01"
              title={t("idx1Title")}
              question={t("idx1Question")}
              description={t("idx1Desc")}
              href="/home"
            />
            <IndexRow
              numeral="02"
              title={t("idx2Title")}
              question={t("idx2Question")}
              description={t("idx2Desc")}
              href="/search"
            />
            <IndexRow
              numeral="03"
              title={t("idx3Title")}
              question={t("idx3Question")}
              description={t("idx3Desc")}
              href="/ranking"
            />
            <IndexRow
              numeral="04"
              title={t("idx4Title")}
              question={t("idx4Question")}
              description={t("idx4Desc")}
              href="/compass"
            />
            <IndexRow
              numeral="05"
              title={t("idx5Title")}
              question={t("idx5Question")}
              description={t("idx5Desc")}
              href="/timeline"
              last
            />
          </div>
        </div>
      </section>

      {/* ── Garanzie ───────────────────────────────────────────── */}
      <section id="garanzie" className="px-6 py-14 sm:py-20 bg-primary text-primary-foreground">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="II" title={t("sec2Title")} inverted />

          <div className="mt-12 grid md:grid-cols-3 gap-x-12 gap-y-10">
            <Guarantee
              index="a"
              title={t("g1Title")}
              body={t("g1Body")}
            />
            <Guarantee
              index="b"
              title={t("g2Title")}
              body={t("g2Body")}
            />
            <Guarantee
              index="c"
              title={t("g3Title")}
              body={t("g3Body")}
            />
          </div>

          {/* Colophon line */}
          <p className="mt-16 pt-6 border-t border-primary-foreground/20 text-sm text-primary-foreground/70 leading-relaxed">
            {t("colophonStats")}
          </p>
        </div>
      </section>

      {/* ── L'iter di ogni domanda ─────────────────────────────── */}
      <section id="pipeline" className="px-6 py-14 sm:py-20">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="III" title={t("sec3Title")} />
          <p className="mt-6 text-muted-foreground max-w-xl">
            {t("iterIntro")}
          </p>

          <ol className="mt-12 grid sm:grid-cols-2 gap-x-16">
            {([1, 2, 3, 4, 5, 6, 7, 8] as const).map((n, i) => {
              const item = { title: t(`iter${n}Title` as never) as string, desc: t(`iter${n}Desc` as never) as string };
              return (
              <li
                key={item.title}
                className="flex gap-5 py-4 border-b border-border"
              >
                <span className="[font-family:var(--font-display)] text-lg text-primary/50 tabular-nums leading-6 select-none">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p className="text-[15px] leading-relaxed">
                  <span className="font-medium">{item.title}</span>
                  <span className="text-muted-foreground"> — {item.desc}</span>
                </p>
              </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* ── Chiusura ───────────────────────────────────────────── */}
      <section id="inizia" className="px-6 pt-8 pb-24">
        <div className="max-w-6xl mx-auto border-t-2 border-foreground pt-14">
          <div className="grid lg:grid-cols-12 gap-8 items-end">
            <h2 className="lg:col-span-8 [font-family:var(--font-display)] text-4xl sm:text-5xl font-medium tracking-tight leading-[1.08] text-balance">
              {t("closingHeadline")}
            </h2>
            <div className="lg:col-span-4 lg:text-right">
              <Link
                href="/home"
                className="group inline-flex w-full sm:w-auto justify-center items-center gap-3 bg-primary text-primary-foreground px-7 py-3.5 text-[15px] font-medium tracking-wide hover:bg-foreground transition-colors cursor-pointer"
              >
                {t("ctaStart")}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Colophon ───────────────────────────────────────────── */}
      <footer className="px-6 py-10 border-t border-border">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2.5">
            <span className="flex h-6 w-6 items-center justify-center bg-primary">
              <Image src="/logo.svg" alt="" width={15} height={15} />
            </span>
            <span className="[font-family:var(--font-display)] text-sm font-medium text-foreground">
              ParliamentRAG
            </span>
          </div>
          <p className="text-center leading-relaxed">
            {t("footerThesis")} · {t("footerAuthors")}
          </p>
          <p className="flex items-center gap-4">
            <a
              href="https://github.com/Emeierkeio/thesis-ParliamentRAG"
              target="_blank"
              rel="noopener noreferrer"
              className="border-b border-border hover:border-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}

/* ── Section rule — newspaper divider with roman numeral ───────── */
function SectionRule({
  numeral,
  title,
  inverted = false,
}: {
  numeral: string;
  title: string;
  inverted?: boolean;
}) {
  return (
    <div
      className={`flex items-baseline gap-4 border-b pb-3 ${
        inverted ? "border-primary-foreground/30" : "border-foreground"
      }`}
    >
      <span
        className={`[font-family:var(--font-display)] italic text-lg ${
          inverted ? "text-primary-foreground/60" : "text-primary/60"
        }`}
      >
        {numeral}.
      </span>
      <h2 className="[font-family:var(--font-display)] text-2xl sm:text-3xl font-medium tracking-tight">
        {title}
      </h2>
    </div>
  );
}

/* ── Index row — table-of-contents entry ───────────────────────── */
function IndexRow({
  numeral,
  title,
  question,
  description,
  href,
  last = false,
}: {
  numeral: string;
  title: string;
  question: string;
  description: string;
  href: string;
  last?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`group grid sm:grid-cols-12 gap-x-6 gap-y-2 py-7 px-2 -mx-2 items-baseline border-border transition-colors hover:bg-accent/60 cursor-pointer ${
        last ? "" : "border-b"
      }`}
    >
      <span className="sm:col-span-1 [font-family:var(--font-display)] text-lg text-primary/40 tabular-nums group-hover:text-primary transition-colors">
        {numeral}
      </span>
      <div className="sm:col-span-3">
        <h3 className="[font-family:var(--font-display)] text-xl font-medium tracking-tight">
          {title}
        </h3>
      </div>
      <div className="sm:col-span-7">
        <p className="[font-family:var(--font-display)] italic text-[15px] text-foreground/80 mb-1.5">
          «{question}»
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
      <span className="sm:col-span-1 justify-self-end self-center hidden sm:block">
        <ArrowRight className="h-4 w-4 text-muted-foreground/40 transition-all group-hover:text-primary group-hover:translate-x-1" />
      </span>
    </Link>
  );
}

/* ── Guarantee — annotated clause on ink background ────────────── */
function Guarantee({
  index,
  title,
  body,
}: {
  index: string;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-4">
      <span className="[font-family:var(--font-display)] italic text-lg text-primary-foreground/50 leading-7 select-none">
        {index})
      </span>
      <div>
        <h3 className="[font-family:var(--font-display)] text-xl font-medium mb-2">
          {title}
        </h3>
        <p className="text-sm leading-relaxed text-primary-foreground/75">
          {body}
        </p>
      </div>
    </div>
  );
}

/* ── Rotating headline — typeset fill-in on a ruled line ───────── */
/* All topics are stacked in the same grid cell so the headline always
   reserves the height of the tallest one — no layout shift on rotation. */
function RotatingHero({
  index,
  isAnimating,
}: {
  index: number;
  isAnimating: boolean;
}) {
  const t = useTranslations("Landing");

  return (
    <h1 className="[font-family:var(--font-display)] text-[clamp(2.25rem,11.5vw,2.75rem)] sm:text-6xl lg:text-[4.25rem] font-medium tracking-tight leading-[1.06]">
      {t("heroLine1")}
      <br />
      {t("heroLine2")}
      <br />
      <span className="inline-grid max-w-full align-top">
        {TOPIC_KEYS.map((key, i) => {
          const active = i === index;
          return (
            <span
              key={key}
              aria-hidden={active ? undefined : true}
              className={`[grid-area:1/1] justify-self-start italic text-primary transition-opacity duration-300 ease-out motion-reduce:transition-none ${
                active ? "" : "pointer-events-none select-none"
              }`}
              style={{
                opacity: active && !isAnimating ? 1 : 0,
                visibility: active ? "visible" : "hidden",
              }}
            >
              <span className="[box-decoration-break:clone] border-b-[3px] border-primary/25">
                {t(`topics.${key}` as never) as string}?
              </span>
            </span>
          );
        })}
      </span>
    </h1>
  );
}

/* ── Side TOC — roman numerals in the margin ───────────────────── */
const TOC_ITEMS = [
  { id: "hero", labelKey: "tocFirstPage", numeral: "·" },
  { id: "strumenti", labelKey: "tocInstruments", numeral: "I" },
  { id: "garanzie", labelKey: "tocGuarantees", numeral: "II" },
  { id: "pipeline", labelKey: "tocIter", numeral: "III" },
  { id: "inizia", labelKey: "tocStart", numeral: "→" },
] as const;

function SideTOC() {
  const t = useTranslations("Landing");
  const [active, setActive] = useState<string>("hero");
  const [visible, setVisible] = useState(false);
  const [overInverted, setOverInverted] = useState(false);

  useEffect(() => {
    const sectionEls = TOC_ITEMS.map(({ id }) =>
      document.getElementById(id)
    ).filter(Boolean) as HTMLElement[];

    const onScroll = () => {
      setVisible(window.scrollY > 200);
      const scrollY = window.scrollY + window.innerHeight / 3;
      let current: string = TOC_ITEMS[0].id;
      for (const el of sectionEls) {
        if (el.offsetTop <= scrollY) {
          current = el.id;
        }
      }
      setActive(current);

      // The TOC is vertically centered: swap to light colors while its
      // midpoint overlaps the dark "garanzie" section (bg-primary)
      const inverted = document.getElementById("garanzie");
      if (inverted) {
        const midY = window.scrollY + window.innerHeight / 2;
        setOverInverted(
          midY >= inverted.offsetTop &&
            midY <= inverted.offsetTop + inverted.offsetHeight
        );
      }
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <nav
      className="fixed left-6 top-1/2 -translate-y-1/2 z-40 hidden xl:flex flex-col items-start gap-0.5 transition-opacity duration-300"
      style={{ opacity: visible ? 1 : 0, pointerEvents: visible ? "auto" : "none" }}
      aria-label="Navigazione sezioni"
    >
      {TOC_ITEMS.map(({ id, labelKey, numeral }) => {
        const label = t(labelKey as never) as string;
        const isActive = active === id;
        return (
          <button
            key={id}
            onClick={() => scrollTo(id)}
            className="group flex items-center gap-3 py-1.5 cursor-pointer"
            aria-current={isActive ? "true" : undefined}
          >
            <span
              className={`[font-family:var(--font-display)] italic w-5 text-right text-sm transition-colors duration-200 ${
                isActive
                  ? overInverted
                    ? "text-primary-foreground"
                    : "text-primary"
                  : overInverted
                    ? "text-primary-foreground/40 group-hover:text-primary-foreground/80"
                    : "text-muted-foreground/40 group-hover:text-muted-foreground"
              }`}
            >
              {numeral}
            </span>
            <span
              className={`text-[11px] font-medium transition-all duration-200 ${
                isActive
                  ? `opacity-100 translate-x-0 ${overInverted ? "text-primary-foreground" : "text-foreground"}`
                  : `opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 ${
                      overInverted
                        ? "text-primary-foreground/60"
                        : "text-muted-foreground/60"
                    }`
              }`}
            >
              {label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}


/* ── Language menu — compact editorial dropdown for the masthead ── */
function LanguageMenu() {
  const locale = useLocale();
  const current = LOCALES.find((l) => l.code === locale) ?? LOCALES[0];

  const switchTo = (nextLocale: string) => {
    if (nextLocale === locale) return;
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; SameSite=Lax`;
    const qs = nextLocale === "it" ? "" : `?lang=${nextLocale}`;
    window.location.href = `/${qs}`;
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className="inline-flex items-center gap-1.5 uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          aria-label="Language"
        >
          <Globe className="h-3 w-3" />
          {current.code}
        </button>
      </PopoverTrigger>
      <PopoverContent side="bottom" align="end" className="w-[170px] p-1.5">
        {LOCALES.map((l) => (
          <button
            key={l.code}
            onClick={() => switchTo(l.code)}
            className={`flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] transition-colors cursor-pointer ${
              l.code === locale
                ? "bg-accent text-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            }`}
          >
            <span className="w-6 text-[10px] uppercase tracking-wide text-muted-foreground/60">{l.code}</span>
            <span className="flex-1 text-left">{l.label}</span>
            {l.code === locale && <Check className="h-3.5 w-3.5" />}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
