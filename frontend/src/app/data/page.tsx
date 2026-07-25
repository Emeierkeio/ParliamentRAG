"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { Fraunces } from "next/font/google";
import { ArrowLeft, ArrowUpRight, Download } from "lucide-react";

const fraunces = Fraunces({
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

/* ── Graph numbers — from the live KG (schema v2, leg. 19) ─────── */
const STATS = [
  { value: "455", key: "stPeople" },
  { value: "45.666", key: "stSpeeches" },
  { value: "694", key: "stSessions" },
  { value: "32.855", key: "stActs" },
  { value: "16.787", key: "stVotes" },
  { value: "6,3 mln", key: "stIndVotes" },
  { value: "1.714", key: "stEurovoc" },
  { value: "863.834", key: "stTriples" },
] as const;

/* ── Real triples from the RDF dump (deputy p307394, abridged) ─── */
const TURTLE_LINES: { text: string; hl?: "uri" | "pred" | "lit" }[] = [
  { text: "@prefix foaf: <http://xmlns.com/foaf/0.1/> ." },
  { text: "@prefix ocd:  <http://dati.camera.it/ocd/> ." },
  { text: "@prefix org:  <http://www.w3.org/ns/org#> ." },
  { text: "@prefix pr:   <https://w3id.org/parliamentrag/ontology#> ." },
  { text: "" },
  { text: "<http://dati.camera.it/ocd/persona.rdf/p307394>", hl: "uri" },
  { text: "    a foaf:Person, ocd:deputato ;", hl: "pred" },
  { text: '    foaf:givenName  "DAVIDE" ;', hl: "lit" },
  { text: '    foaf:familyName "AIELLO" ;', hl: "lit" },
  { text: "    ocd:rif_mandatoCamera <…/mandatoCamera.rdf/mc19_307394> ." },
  { text: "" },
  { text: "<…/membership/p307394_m5s_2022-10-18>", hl: "uri" },
  { text: "    a org:Membership ;", hl: "pred" },
  { text: "    org:member       <…/persona.rdf/p307394> ;" },
  { text: "    org:organization <…/group/m5s> ;" },
  { text: '    pr:startDate "2022-10-18"^^xsd:date .', hl: "lit" },
];

/* ── Ontology alignment — vocab column is not translated ───────── */
const MAPPING_ROWS = [
  { n: "r1", vocab: "foaf:Person + ocd:deputato" },
  { n: "r2", vocab: "org:Organization (W3C)" },
  { n: "r3", vocab: "org:Membership" },
  { n: "r4", vocab: "skos:Concept — EuroVoc" },
  { n: "r5", vocab: "≈ Akoma Ntoso" },
  { n: "r6", vocab: "ocd:votazione / ocd:voto" },
  { n: "r7", vocab: "PROV-O" },
] as const;

export default function DataPage() {
  const t = useTranslations("DataPage");

  return (
    <div
      className={`${fraunces.variable} min-h-screen bg-background text-foreground`}
    >
      {/* ── Masthead-lite ──────────────────────────────────────── */}
      <header className="border-b-2 border-foreground">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between py-5">
          <Link href="/" className="flex items-center gap-3">
            <Image src="/logo-blue.svg" alt="" width={38} height={21} />
            <span className="[font-family:var(--font-display)] text-xl sm:text-2xl font-semibold tracking-tight">
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

      {/* ── Hero ───────────────────────────────────────────────── */}
      <section className="px-6 pt-14 sm:pt-20 pb-14">
        <div className="max-w-6xl mx-auto">
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            {t("heroKicker")}
          </p>
          <h1 className="mt-4 [font-family:var(--font-display)] text-4xl sm:text-6xl font-medium tracking-tight leading-[1.06] max-w-3xl text-balance">
            {t("heroTitle")}
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground max-w-2xl">
            {t.rich("heroSub", {
              strong: (chunks) => (
                <span className="text-foreground">{chunks}</span>
              ),
            })}
          </p>
        </div>
      </section>

      {/* ── I. The graph in numbers ────────────────────────────── */}
      <section className="px-6 py-14 sm:py-16">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="I" title={t("sec1Title")} />
          <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-10">
            {STATS.map((s) => (
              <div key={s.key}>
                <p className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-medium tracking-tight text-primary tabular-nums">
                  {s.value}
                </p>
                <p className="mt-1.5 text-sm text-muted-foreground leading-snug">
                  {t(s.key)}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-10 pt-4 border-t border-border text-sm text-muted-foreground max-w-2xl">
            {t("sec1Note")}
          </p>
        </div>
      </section>

      {/* ── II. The semantic web, in three ideas ───────────────── */}
      <section className="px-6 py-14 sm:py-16 bg-primary text-primary-foreground">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="II" title={t("sec2Title")} inverted />
          <div className="mt-12 grid md:grid-cols-3 gap-x-12 gap-y-10">
            {(["idea1", "idea2", "idea3"] as const).map((idea, i) => (
              <div key={idea} className="flex gap-4">
                <span className="[font-family:var(--font-display)] italic text-lg text-primary-foreground/50 leading-7 select-none">
                  {String.fromCharCode(97 + i)})
                </span>
                <div>
                  <h3 className="[font-family:var(--font-display)] text-xl font-medium mb-2">
                    {t(`${idea}Title`)}
                  </h3>
                  <p className="text-sm leading-relaxed text-primary-foreground/75">
                    {t(`${idea}Body`)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── III. A deputy, in triples ──────────────────────────── */}
      <section className="px-6 py-14 sm:py-16">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="III" title={t("sec3Title")} />
          <p className="mt-6 text-muted-foreground max-w-2xl">{t("sec3Intro")}</p>

          <div className="mt-10 grid lg:grid-cols-12 gap-10 lg:gap-8 items-start">
            <figure className="lg:col-span-7 min-w-0">
              <pre className="overflow-x-auto border border-border bg-accent/40 px-5 py-4 text-[12.5px] leading-[1.7] font-mono">
                {TURTLE_LINES.map((line, i) => (
                  <code
                    key={i}
                    className={`block whitespace-pre ${
                      line.hl === "uri"
                        ? "text-primary"
                        : line.hl === "lit"
                          ? "text-foreground"
                          : line.hl === "pred"
                            ? "text-foreground/80"
                            : "text-muted-foreground"
                    }`}
                  >
                    {line.text || " "}
                  </code>
                ))}
              </pre>
              <figcaption className="mt-3 text-xs text-muted-foreground">
                {t("exCaption")}
              </figcaption>
            </figure>

            <div className="lg:col-span-5 lg:pl-8 lg:border-l border-border space-y-6">
              {(["ex1", "ex2", "ex3"] as const).map((ex, i) => (
                <div key={ex} className="flex gap-4">
                  <span className="[font-family:var(--font-display)] text-lg text-primary/50 tabular-nums leading-6 select-none">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <p className="text-sm leading-relaxed">
                    <span className="font-medium">{t(`${ex}Title`)}</span>
                    <span className="text-muted-foreground">
                      {" "}
                      — {t(`${ex}Body`)}
                    </span>
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── IV. Speaking the language of official data ─────────── */}
      <section className="px-6 py-14 sm:py-16">
        <div className="max-w-6xl mx-auto">
          <SectionRule numeral="IV" title={t("sec4Title")} />
          <p className="mt-6 text-muted-foreground max-w-2xl">{t("sec4Intro")}</p>

          <div className="mt-10 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-foreground text-left">
                  <th className="py-3 pr-6 font-medium text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                    {t("mapCol1")}
                  </th>
                  <th className="py-3 pr-6 font-medium text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                    {t("mapCol2")}
                  </th>
                  <th className="py-3 font-medium text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                    {t("mapCol3")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {MAPPING_ROWS.map((row) => (
                  <tr key={row.n} className="border-b border-border align-top">
                    <td className="py-3.5 pr-6 font-medium">
                      {t(`${row.n}c`)}
                    </td>
                    <td className="py-3.5 pr-6 font-mono text-[12.5px] text-primary whitespace-nowrap">
                      {row.vocab}
                    </td>
                    <td className="py-3.5 text-muted-foreground leading-relaxed">
                      {t(`${row.n}m`)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── V. Download & reuse ────────────────────────────────── */}
      <section className="px-6 pt-8 pb-24">
        <div className="max-w-6xl mx-auto border-t-2 border-foreground pt-14">
          <SectionRule numeral="V" title={t("sec5Title")} />
          <p className="mt-6 text-muted-foreground max-w-2xl">{t("sec5Intro")}</p>

          <div className="mt-10 grid md:grid-cols-2 gap-6">
            <FileCard
              title={t("fileKgTitle")}
              format="Turtle · 172 MB"
              body={t("fileKgDesc")}
              note={t("zenodoNote")}
            />
            <FileCard
              title={t("fileVotesTitle")}
              format="N-Triples · 3,8 GB"
              body={t("fileVotesDesc")}
              note={t("zenodoNote")}
            />
          </div>

          <div className="mt-10 border-l-2 border-primary/40 bg-primary/[0.04] px-5 py-4 max-w-3xl">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
              {t("reproTitle")}
            </p>
            <p className="text-sm leading-relaxed text-foreground/85">
              {t.rich("reproBody", {
                code: (chunks) => (
                  <code className="font-mono text-[12.5px] bg-accent px-1.5 py-0.5">
                    {chunks}
                  </code>
                ),
              })}{" "}
              <a
                href="https://github.com/Emeierkeio/ParliamentRAG"
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-baseline gap-1 text-foreground border-b border-border hover:border-foreground transition-colors"
              >
                GitHub
                <ArrowUpRight className="h-3 w-3 self-center" />
              </a>
            </p>
          </div>

          <p className="mt-8 text-xs text-muted-foreground max-w-3xl leading-relaxed">
            {t("licenseNote")}
          </p>
        </div>
      </section>
    </div>
  );
}

/* ── Section rule — same newspaper divider as the landing ──────── */
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

/* ── File card — dataset artefact with format tag ──────────────── */
function FileCard({
  title,
  format,
  body,
  note,
}: {
  title: string;
  format: string;
  body: string;
  note: string;
}) {
  return (
    <div className="border border-border px-6 py-5 flex flex-col">
      <div className="flex items-start justify-between gap-4">
        <h3 className="[font-family:var(--font-display)] text-xl font-medium tracking-tight">
          {title}
        </h3>
        <Download className="h-4 w-4 text-muted-foreground/50 shrink-0 mt-1.5" />
      </div>
      <p className="mt-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
        {format}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground flex-1">
        {body}
      </p>
      <p className="mt-4 pt-3 border-t border-border text-xs text-primary font-medium">
        {note}
      </p>
    </div>
  );
}
