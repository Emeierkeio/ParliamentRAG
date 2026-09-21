"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Sidebar } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { graphQuery } from "@/lib/graph";
import { config, getGroupAbbrev, getGroupColor } from "@/config";
import { toTitleCase } from "@/lib/utils";

interface GroupRow {
  name: string;
  members: number;
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

function groupSlug(name: string): string {
  return getGroupAbbrev(name).toLowerCase();
}

/** Se due nomi mappano sullo stesso slug tiene quello con più componenti.
 * Le righe arrivano già ordinate per componenti in senso decrescente. */
function dedupeBySlug(rows: GroupRow[]): GroupRow[] {
  const seen = new Set<string>();
  const out: GroupRow[] = [];
  for (const row of rows) {
    const slug = groupSlug(row.name);
    if (seen.has(slug)) continue;
    seen.add(slug);
    out.push(row);
  }
  return out;
}

export default function GruppiPage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const t = useTranslations("Entities");
  const [groups, setGroups] = useState<GroupRow[] | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setError(false);
    setGroups(null);
    graphQuery<GroupRow>(DIRECTORY_QUERY)
      .then((rows) => setGroups(dedupeBySlug(rows)))
      .catch(() => setError(true));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
          <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-semibold tracking-tight">
            {t("groupsTitle")}
          </h1>
          <p className="mt-2 text-muted-foreground">{t("groupsIntro")}</p>

          <div className="mt-8">
            {error ? (
              <div className="border-b py-10 text-center">
                <p className="text-muted-foreground">{t("errorLoad")}</p>
                <button
                  type="button"
                  onClick={load}
                  className="mt-3 text-sm underline underline-offset-4 hover:text-foreground"
                >
                  {t("retry")}
                </button>
              </div>
            ) : groups === null ? (
              <ul aria-hidden>
                {Array.from({ length: 8 }).map((_, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-3 border-b py-4"
                  >
                    <span className="h-2.5 w-2.5 rounded-full bg-muted animate-pulse" />
                    <span className="h-4 flex-1 max-w-72 rounded bg-muted animate-pulse" />
                    <span className="ml-auto h-4 w-24 rounded bg-muted animate-pulse" />
                  </li>
                ))}
              </ul>
            ) : groups.length === 0 ? (
              <p className="border-b py-10 text-center text-muted-foreground">
                {t("noResults")}
              </p>
            ) : (
              <ul>
                {groups.map((g) => (
                  <li key={g.name}>
                    <Link
                      href={`/gruppi/${groupSlug(g.name)}`}
                      className="group flex items-baseline gap-3 border-b py-4 transition-colors hover:bg-muted/40"
                    >
                      <span
                        className="h-2.5 w-2.5 rounded-full inline-block self-center shrink-0"
                        style={{ backgroundColor: getGroupColor(g.name) }}
                        aria-hidden
                      />
                      <span className="min-w-0 truncate group-hover:underline underline-offset-4">
                        {groupLabel(g.name)}
                      </span>
                      <span className="ml-auto shrink-0 font-mono text-sm text-muted-foreground tabular-nums">
                        {t("membersCount", { count: g.members })}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
