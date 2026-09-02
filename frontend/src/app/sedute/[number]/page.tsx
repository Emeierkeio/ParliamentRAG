"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";

import { AppHeader } from "@/components/layout/AppHeader";
import { VotesList } from "@/components/timeline/VotesList";
import { graphQuery } from "@/lib/graph";
import { getSessionVotes } from "@/lib/timeline-api";
import type { VoteInfo } from "@/types/timeline";

interface DebateRow {
  id: string;
  title: string;
}

interface SessionData {
  date: string;
  debates: DebateRow[];
}

/** idSeduta camera.it vuole 4 cifre (705 -> "0705"). */
function paddedSessionNumber(n: number): string {
  return String(n).padStart(4, "0");
}

function officialRecordUrl(n: number): string {
  return `https://www.camera.it/leg19/410?idSeduta=${paddedSessionNumber(n)}&tipo=stenografico`;
}

/** Ancora dello stenografico per un dibattito, se l'id segue il pattern noto
 *  (es. "leg19_sed705_tit00010" -> "#sed0705.stenografico.tit00010"). */
function debateRecordUrl(n: number, debateId: string): string | null {
  const m = debateId.match(/leg\d+_sed\d+_(.+)/);
  if (!m) return null;
  return `${officialRecordUrl(n)}#sed${paddedSessionNumber(n)}.stenografico.${m[1]}`;
}

export default function SessionDetailPage() {
  const t = useTranslations("Entities");
  const locale = useLocale();
  const params = useParams();

  const rawNumber = Array.isArray(params.number) ? params.number[0] : params.number;
  const sessionNumber = useMemo(() => {
    if (!rawNumber || !/^\d+$/.test(rawNumber)) return null;
    const n = parseInt(rawNumber, 10);
    return n > 0 ? n : null;
  }, [rawNumber]);

  const [session, setSession] = useState<SessionData | null>(null);
  const [votes, setVotes] = useState<VoteInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (sessionNumber === null) {
      setLoading(false);
      setError(true);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const rows = await graphQuery<{ date: string; id: string | null; title: string | null }>(
        `MATCH (s:Session {number: ${sessionNumber}})
         OPTIONAL MATCH (s)-[:HAS_DEBATE]->(d:Debate)
         RETURN s.date AS date, d.id AS id, d.title AS title
         ORDER BY d.order`
      );
      if (rows.length === 0) {
        setSession(null);
      } else {
        setSession({
          date: rows[0].date,
          debates: rows
            .filter((r): r is { date: string; id: string; title: string } => !!r.id)
            .map((r) => ({ id: r.id, title: r.title ?? r.id })),
        });
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }

    // I voti arrivano da un endpoint separato: se fallisce la sezione
    // semplicemente non compare, la pagina resta utile.
    try {
      const v = await getSessionVotes(`leg19_sed${sessionNumber}`);
      setVotes(Array.isArray(v) ? v : []);
    } catch {
      setVotes([]);
    }
  }, [sessionNumber]);

  useEffect(() => {
    void load();
  }, [load]);

  const formattedDate = useMemo(() => {
    if (!session?.date) return null;
    const d = new Date(session.date);
    if (isNaN(d.getTime())) return session.date;
    return new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(d);
  }, [session?.date, locale]);

  return (
    <div className="flex flex-col min-h-dvh bg-background pb-[calc(4.75rem+env(safe-area-inset-bottom))] md:pb-0">
      <AppHeader />
      <main className="flex-1">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
          <Link
            href="/sedute"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {t("backToList")}
          </Link>

          {loading ? (
            <div className="mt-8 space-y-4 animate-pulse">
              <div className="h-9 w-2/3 bg-muted rounded" />
              <div className="h-4 w-40 bg-muted rounded" />
              <div className="h-4 w-full bg-muted rounded" />
              <div className="h-4 w-5/6 bg-muted rounded" />
            </div>
          ) : error ? (
            <div className="mt-10 border-b border-border pb-6">
              <p className="text-sm text-muted-foreground">{t("errorLoad")}</p>
              {sessionNumber !== null && (
                <button
                  type="button"
                  onClick={() => void load()}
                  className="mt-3 text-sm underline underline-offset-2 hover:text-foreground transition-colors"
                >
                  {t("retry")}
                </button>
              )}
            </div>
          ) : !session ? (
            <div className="mt-10 border-b border-border pb-6">
              <p className="text-sm text-muted-foreground">{t("noResults")}</p>
            </div>
          ) : (
            <>
              <h1 className="mt-6 [font-family:var(--font-display)] text-3xl sm:text-4xl font-semibold tracking-tight">
                {t("sessionTitle", { number: sessionNumber! })}
              </h1>
              {formattedDate && (
                <p className="mt-2 font-mono text-sm text-muted-foreground">{formattedDate}</p>
              )}

              <a
                href={officialRecordUrl(sessionNumber!)}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <span className="inline-block h-2 w-2 bg-current" />
                {t("openSource")}
              </a>

              {/* Dibattiti */}
              <section className="mt-10">
                <h2 className="[font-family:var(--font-display)] text-xl font-medium tracking-tight border-b border-border pb-2">
                  {t("debatesTitle")}
                </h2>
                {session.debates.length === 0 ? (
                  <p className="py-4 text-sm text-muted-foreground">{t("noResults")}</p>
                ) : (
                  <ul>
                    {session.debates.map((debate, i) => {
                      const href = debateRecordUrl(sessionNumber!, debate.id);
                      return (
                        <li
                          key={debate.id}
                          className="flex items-baseline gap-4 border-b border-border py-3"
                        >
                          <span className="font-mono text-xs text-muted-foreground tabular-nums shrink-0">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          {href ? (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm leading-relaxed hover:underline underline-offset-2"
                            >
                              {debate.title}
                            </a>
                          ) : (
                            <span className="text-sm leading-relaxed">{debate.title}</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>

              {/* Voti: la sezione esiste solo se ci sono voti */}
              {votes.length > 0 && (
                <section className="mt-10">
                  <h2 className="[font-family:var(--font-display)] text-xl font-medium tracking-tight border-b border-border pb-2 mb-3">
                    {t("votesTitle")}
                  </h2>
                  <VotesList votes={votes} />
                </section>
              )}
            </>
          )}

          {/* Navigazione precedente/successiva */}
          {sessionNumber !== null && (
            <nav className="mt-12 flex items-center justify-between border-t border-border pt-4">
              {sessionNumber > 1 ? (
                <Link
                  href={`/sedute/${sessionNumber - 1}`}
                  className="font-mono text-sm text-muted-foreground hover:text-foreground transition-colors tabular-nums"
                >
                  &larr; {sessionNumber - 1}
                </Link>
              ) : (
                <span />
              )}
              <Link
                href={`/sedute/${sessionNumber + 1}`}
                className="font-mono text-sm text-muted-foreground hover:text-foreground transition-colors tabular-nums"
              >
                {sessionNumber + 1} &rarr;
              </Link>
            </nav>
          )}
        </div>
      </main>
    </div>
  );
}
