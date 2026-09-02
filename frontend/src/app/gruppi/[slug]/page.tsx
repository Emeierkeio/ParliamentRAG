"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";
import { AppHeader } from "@/components/layout/AppHeader";
import { GroupMemberAvatar } from "@/components/entities/GroupMemberAvatar";
import { graphQuery, deputySlug } from "@/lib/graph";
import { config, getGroupAbbrev, getGroupColor } from "@/config";
import { toTitleCase } from "@/lib/utils";

interface GroupRow {
  name: string;
  members: number;
}

interface MemberRow {
  id: string;
  first_name: string;
  last_name: string;
  photo: string | null;
}

const DIRECTORY_QUERY =
  "MATCH (g:ParliamentaryGroup)<-[:MEMBER_OF_GROUP]-(d:Deputy) " +
  "RETURN g.name AS name, count(d) AS members ORDER BY members DESC";

function groupLabel(name: string): string {
  const known = (
    config.politicalGroups as Record<string, { label: string }>
  )[name];
  return known?.label ?? toTitleCase(name);
}

/** Nome canonico per slug: il gruppo il cui abbreviativo coincide; a parità
 * di slug vince quello con più componenti (le righe sono già ordinate). */
function resolveGroup(rows: GroupRow[], slug: string): GroupRow | null {
  return (
    rows.find((r) => getGroupAbbrev(r.name).toLowerCase() === slug) ?? null
  );
}

function escapeCypherString(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

type State =
  | { phase: "loading" }
  | { phase: "error" }
  | { phase: "notFound" }
  | { phase: "ready"; group: GroupRow; members: MemberRow[] };

export default function GruppoDettaglioPage() {
  const t = useTranslations("Entities");
  const params = useParams<{ slug: string }>();
  const slug = (params?.slug ?? "").toLowerCase();
  const [state, setState] = useState<State>({ phase: "loading" });

  const load = useCallback(() => {
    if (!slug) return;
    setState({ phase: "loading" });
    graphQuery<GroupRow>(DIRECTORY_QUERY)
      .then((rows) => {
        const group = resolveGroup(rows, slug);
        if (!group) {
          setState({ phase: "notFound" });
          return null;
        }
        const membersQuery =
          `MATCH (g:ParliamentaryGroup {name: "${escapeCypherString(group.name)}"})` +
          "<-[:MEMBER_OF_GROUP]-(d:Deputy) " +
          "RETURN d.id AS id, d.first_name AS first_name, d.last_name AS last_name, " +
          "d.photo AS photo ORDER BY d.last_name, d.first_name";
        return graphQuery<MemberRow>(membersQuery).then((members) =>
          setState({ phase: "ready", group, members })
        );
      })
      .catch(() => setState({ phase: "error" }));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const label =
    state.phase === "ready" ? groupLabel(state.group.name) : null;

  return (
    <div className="flex flex-col min-h-dvh bg-background pb-[calc(4.75rem+env(safe-area-inset-bottom))] md:pb-0">
      <AppHeader />
      <main className="flex-1">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
          <Link
            href="/gruppi"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            {t("backToList")}
          </Link>

          {state.phase === "error" && (
            <div className="mt-10 border-b py-10 text-center">
              <p className="text-muted-foreground">{t("errorLoad")}</p>
              <button
                type="button"
                onClick={load}
                className="mt-3 text-sm underline underline-offset-4 hover:text-foreground"
              >
                {t("retry")}
              </button>
            </div>
          )}

          {state.phase === "notFound" && (
            <div className="mt-10 border-b py-10 text-center">
              <p className="text-muted-foreground">{t("noResults")}</p>
              <Link
                href="/gruppi"
                className="mt-3 inline-block text-sm underline underline-offset-4 hover:text-foreground"
              >
                {t("backToList")}
              </Link>
            </div>
          )}

          {state.phase === "loading" && (
            <div className="mt-8" aria-hidden>
              <div className="flex items-center gap-3">
                <span className="h-3 w-3 rounded-full bg-muted animate-pulse" />
                <span className="h-8 w-64 rounded bg-muted animate-pulse" />
              </div>
              <span className="mt-3 block h-4 w-28 rounded bg-muted animate-pulse" />
              <div className="mt-8 grid gap-x-8 sm:grid-cols-2">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 border-b py-3">
                    <span className="h-8 w-8 rounded-full bg-muted animate-pulse" />
                    <span className="h-4 w-40 rounded bg-muted animate-pulse" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {state.phase === "ready" && label && (
            <>
              <header className="mt-8">
                <div className="flex items-center gap-3">
                  <span
                    className="h-3 w-3 rounded-full inline-block shrink-0"
                    style={{ backgroundColor: getGroupColor(state.group.name) }}
                    aria-hidden
                  />
                  <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-semibold tracking-tight">
                    {label}
                  </h1>
                </div>
                <p className="mt-2 font-mono text-sm text-muted-foreground tabular-nums">
                  {t("membersCount", { count: state.group.members })}
                </p>
              </header>

              <nav className="mt-8 flex flex-wrap gap-x-6 gap-y-2 border-t pt-4 text-sm">
                <Link
                  href="/compass"
                  className="text-muted-foreground transition-colors hover:text-foreground hover:underline underline-offset-4"
                >
                  {t("positionsOf")}
                </Link>
                <Link
                  href="/ranking"
                  className="text-muted-foreground transition-colors hover:text-foreground hover:underline underline-offset-4"
                >
                  {t("whoKnowsMost")}
                </Link>
                <Link
                  href={`/search?q=${encodeURIComponent(label)}`}
                  className="text-muted-foreground transition-colors hover:text-foreground hover:underline underline-offset-4"
                >
                  {t("actsOfGroup")}
                </Link>
              </nav>

              <section className="mt-10">
                <h2 className="[font-family:var(--font-display)] text-xl font-semibold tracking-tight">
                  {t("membersTitle")}
                </h2>
                {state.members.length === 0 ? (
                  <p className="mt-4 border-b py-8 text-center text-muted-foreground">
                    {t("noResults")}
                  </p>
                ) : (
                  <ul className="mt-4 grid gap-x-8 sm:grid-cols-2">
                    {state.members.map((m) => {
                      const name = toTitleCase(
                        `${m.first_name} ${m.last_name}`.trim()
                      );
                      return (
                        <li key={m.id}>
                          <Link
                            href={`/parlamentari/${deputySlug(m.id)}`}
                            className="group flex items-center gap-3 border-b py-3 transition-colors hover:bg-muted/40"
                          >
                            <GroupMemberAvatar photo={m.photo} name={name} />
                            <span className="min-w-0 truncate group-hover:underline underline-offset-4">
                              {name}
                            </span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
