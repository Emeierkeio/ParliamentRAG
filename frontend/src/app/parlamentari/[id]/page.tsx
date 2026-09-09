"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Sidebar } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { DeputyAvatar } from "@/components/entities/DeputyAvatar";
import { graphQuery, deputyUriFromSlug } from "@/lib/graph";
import { config, getGroupColor } from "@/config";
import { formatDate, toTitleCase } from "@/lib/utils";

interface DeputyProfile {
  first_name: string;
  last_name: string;
  photo: string | null;
  deputy_card: string | null;
  profession: string | null;
  education: string | null;
  institutional_role: string | null;
  group: string | null;
  speeches: number;
  acts: number;
}

interface RecentSpeech {
  id: string;
  text: string | null;
  date: string;
  session_number: number | null;
  debate_title: string | null;
}

const SLUG_RE = /^p\d+$/;

function profileCypher(uri: string): string {
  return (
    `MATCH (d:Deputy {id: "${uri}"}) ` +
    "OPTIONAL MATCH (d)-[:MEMBER_OF_GROUP]->(g:ParliamentaryGroup) WITH d, g " +
    "OPTIONAL MATCH (s:Speech)-[:SPOKEN_BY]->(d) WITH d, g, count(s) AS speeches " +
    "OPTIONAL MATCH (d)-[:PRIMARY_SIGNATORY]->(a:ParliamentaryAct) " +
    "RETURN d.first_name AS first_name, d.last_name AS last_name, d.photo AS photo, " +
    "d.deputy_card AS deputy_card, d.profession AS profession, d.education AS education, " +
    "d.institutional_role AS institutional_role, g.name AS group, speeches, count(a) AS acts"
  );
}

export default function DeputyProfilePage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const t = useTranslations("Entities");
  const tSidebar = useTranslations("Sidebar");
  const params = useParams();
  const slug = typeof params.id === "string" ? params.id : "";
  const validSlug = SLUG_RE.test(slug);

  const [profile, setProfile] = useState<DeputyProfile | null>(null);
  const [loading, setLoading] = useState(validSlug);
  const [error, setError] = useState(!validSlug);
  const [recent, setRecent] = useState<RecentSpeech[]>([]);

  const load = useCallback(async () => {
    if (!validSlug) return;
    setError(false);
    setLoading(true);
    setProfile(null);
    setRecent([]);
    try {
      const uri = deputyUriFromSlug(slug);
      const rows = await graphQuery<DeputyProfile>(profileCypher(uri));
      if (rows.length === 0) {
        setError(true);
        return;
      }
      setProfile(rows[0]);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [slug, validSlug]);

  useEffect(() => {
    load();
  }, [load]);

  // Interventi recenti via Cypher diretto: la ricerca ibrida non puo' farlo,
  // perche' esige una query testuale e il nome del deputato non compare nel
  // testo dei suoi interventi. Se la chiamata fallisce la lista resta vuota
  // e si mostra solo il link alla ricerca completa.
  useEffect(() => {
    if (!profile || !validSlug) return;
    let cancelled = false;
    const uri = deputyUriFromSlug(slug);
    const cypher =
      `MATCH (i:Speech)-[:SPOKEN_BY]->(d:Deputy {id: "${uri}"}) ` +
      "MATCH (i)<-[:CONTAINS_SPEECH]-(:Phase)<-[:HAS_PHASE]-(dib:Debate)<-[:HAS_DEBATE]-(s:Session) " +
      "WITH i, s, dib ORDER BY s.date DESC LIMIT 5 " +
      "OPTIONAL MATCH (i)-[:HAS_CHUNK]->(c:Chunk) " +
      "WITH i, s, dib, c ORDER BY c.index ASC " +
      "WITH i, s, dib, collect(c.text)[0] AS text " +
      "RETURN i.id AS id, text, toString(s.date) AS date, " +
      "s.number AS session_number, dib.title AS debate_title " +
      "ORDER BY date DESC";
    graphQuery<RecentSpeech>(cypher)
      .then((rows) => {
        if (!cancelled) setRecent(rows);
      })
      .catch(() => {
        /* lista nascosta, resta il link viewAllSpeeches */
      });
    return () => {
      cancelled = true;
    };
  }, [profile, slug, validSlug]);

  const fullName = profile
    ? toTitleCase(`${profile.first_name} ${profile.last_name}`)
    : "";
  const searchHref = `/search?q=${encodeURIComponent(fullName)}`;

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
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
          {/* Torna all'elenco */}
          <a
            href="/parlamentari"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t("backToList")}
          </a>

          {error ? (
            <div className="mt-10 border-t border-border py-12 text-center">
              <p className="text-sm text-muted-foreground">{t("errorLoad")}</p>
              {validSlug && (
                <button
                  type="button"
                  onClick={load}
                  className="mt-4 inline-flex h-9 items-center rounded-md border border-border px-4 text-sm transition-colors hover:bg-muted"
                >
                  {t("retry")}
                </button>
              )}
            </div>
          ) : loading || !profile ? (
            <div className="mt-10 space-y-3">
              <div className="h-24 bg-muted motion-safe:animate-pulse rounded-md" />
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-12 bg-muted motion-safe:animate-pulse rounded-md" />
              ))}
            </div>
          ) : (
            <>
              {/* Intestazione profilo */}
              <header className="mt-8 flex items-start gap-5 sm:gap-6">
                <DeputyAvatar
                  photo={profile.photo}
                  firstName={profile.first_name}
                  lastName={profile.last_name}
                  group={profile.group}
                  size={96}
                />
                <div className="min-w-0 pt-1">
                  <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-semibold tracking-tight">
                    {fullName}
                  </h1>
                  {profile.group && (
                    <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ backgroundColor: getGroupColor(profile.group) }}
                      />
                      <span>{(config.politicalGroups as Record<string, { label?: string }>)[profile.group]?.label ?? toTitleCase(profile.group)}</span>
                    </p>
                  )}
                  {profile.institutional_role && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {profile.institutional_role}
                    </p>
                  )}
                </div>
              </header>

              {/* Righe di dettaglio */}
              <div className="mt-10">
                {profile.profession && (
                  <div className="flex flex-col gap-1 border-b border-border py-4 sm:flex-row sm:items-baseline sm:gap-6">
                    <span className="w-32 shrink-0 text-[11px] uppercase tracking-wide text-muted-foreground">
                      {t("profession")}
                    </span>
                    <span className="text-sm text-foreground">{profile.profession}</span>
                  </div>
                )}
                {profile.education && (
                  <div className="flex flex-col gap-1 border-b border-border py-4 sm:flex-row sm:items-baseline sm:gap-6">
                    <span className="w-32 shrink-0 text-[11px] uppercase tracking-wide text-muted-foreground">
                      {t("education")}
                    </span>
                    <span className="text-sm text-foreground">{profile.education}</span>
                  </div>
                )}
                {profile.deputy_card && (
                  <div className="border-b border-border py-4">
                    <a
                      href={profile.deputy_card}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm text-foreground underline-offset-4 transition-colors hover:underline"
                    >
                      <span className="inline-block h-2 w-2 bg-current" />
                      {t("officialCard")}
                    </a>
                  </div>
                )}
              </div>

              {/* Attivita in Aula */}
              <p className="mt-6 font-mono text-sm text-muted-foreground">
                {t("speechesCount", { count: profile.speeches })}
                <span className="mx-2 text-muted-foreground/50">·</span>
                {t("actsCount", { count: profile.acts })}
              </p>

              {/* Interventi recenti */}
              <section className="mt-12">
                <h2 className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  {t("recentSpeeches")}
                </h2>
                {recent.length > 0 && (
                  <div className="mt-2 border-t border-border">
                    {recent.map((s) => (
                      <a
                        key={s.id}
                        href={s.session_number != null ? `/sedute/${s.session_number}` : searchHref}
                        className="block border-b border-border py-3.5 transition-colors hover:bg-muted/40"
                      >
                        <span className="font-mono text-xs text-muted-foreground">
                          {formatDate(s.date)}
                          {s.session_number != null && (
                            <> · {t("sessionTitle", { number: s.session_number })}</>
                          )}
                        </span>
                        {s.debate_title && (
                          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                            {s.debate_title}
                          </p>
                        )}
                        {s.text && (
                          <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-foreground">
                            {s.text}
                          </p>
                        )}
                      </a>
                    ))}
                  </div>
                )}
                <a
                  href={searchHref}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {t("viewAllSpeeches")}
                  <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </section>

              {/* Rimando all'analisi di autorevolezza */}
              <div className="mt-10 border-t border-border pt-5">
                <a
                  href="/ranking"
                  className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {tSidebar("authorityAnalysis")}
                  <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
