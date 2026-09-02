"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { AppHeader } from "@/components/layout/AppHeader";
import { DeputyAvatar } from "@/components/entities/DeputyAvatar";
import { graphQuery, deputySlug } from "@/lib/graph";

// Nomi gruppo dal grafo in maiuscolo: la label canonica vive in config,
// il title-case resta solo come ripiego per nomi non mappati
function groupLabel(name: string): string {
  return (
    (config.politicalGroups as Record<string, { label?: string }>)[name]?.label ??
    toTitleCase(name)
  );
}
import { config, getGroupColor } from "@/config";
import { toTitleCase } from "@/lib/utils";

interface DeputyRow {
  id: string;
  first_name: string;
  last_name: string;
  photo: string | null;
  profession: string | null;
  group: string | null;
}

const DIRECTORY_CYPHER =
  "MATCH (d:Deputy) " +
  "OPTIONAL MATCH (d)-[:MEMBER_OF_GROUP]->(g:ParliamentaryGroup) " +
  "RETURN d.id AS id, d.first_name AS first_name, d.last_name AS last_name, " +
  "d.photo AS photo, d.profession AS profession, g.name AS group " +
  "ORDER BY d.last_name, d.first_name";

export default function DeputiesDirectoryPage() {
  const t = useTranslations("Entities");

  const [deputies, setDeputies] = useState<DeputyRow[] | null>(null);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");

  const load = useCallback(async () => {
    setError(false);
    setDeputies(null);
    try {
      const rows = await graphQuery<DeputyRow>(DIRECTORY_CYPHER);
      setDeputies(rows);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const groups = useMemo(() => {
    if (!deputies) return [];
    const distinct = new Set<string>();
    for (const d of deputies) {
      if (d.group) distinct.add(d.group);
    }
    return Array.from(distinct).sort((a, b) => a.localeCompare(b, "it"));
  }, [deputies]);

  const filtered = useMemo(() => {
    if (!deputies) return [];
    const needle = search.trim().toLowerCase();
    return deputies.filter((d) => {
      if (groupFilter && d.group !== groupFilter) return false;
      if (!needle) return true;
      const fullName = `${d.first_name} ${d.last_name}`.toLowerCase();
      const reversed = `${d.last_name} ${d.first_name}`.toLowerCase();
      return fullName.includes(needle) || reversed.includes(needle);
    });
  }, [deputies, search, groupFilter]);

  return (
    <div className="flex flex-col min-h-dvh bg-background pb-[calc(4.75rem+env(safe-area-inset-bottom))] md:pb-0">
      <AppHeader />
      <main className="flex-1">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
          {/* Intestazione */}
          <header className="space-y-2">
            <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl font-semibold tracking-tight">
              {t("deputiesTitle")}
            </h1>
            <p className="text-muted-foreground">{t("deputiesIntro")}</p>
          </header>

          {/* Filtri */}
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("searchDeputyPlaceholder")}
                className="h-10 w-full rounded-md border border-border bg-background pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-foreground/40"
              />
            </div>
            <select
              value={groupFilter}
              onChange={(e) => setGroupFilter(e.target.value)}
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm outline-none transition-colors focus-visible:border-foreground/40 sm:w-64"
            >
              <option value="">{t("allGroups")}</option>
              {groups.map((g) => (
                <option key={g} value={g}>
                  {toTitleCase(g)}
                </option>
              ))}
            </select>
          </div>

          {/* Stati: caricamento / errore / lista */}
          <div className="mt-6">
            {error ? (
              <div className="border-t border-border py-12 text-center">
                <p className="text-sm text-muted-foreground">{t("errorLoad")}</p>
                <button
                  type="button"
                  onClick={load}
                  className="mt-4 inline-flex h-9 items-center rounded-md border border-border px-4 text-sm transition-colors hover:bg-muted"
                >
                  {t("retry")}
                </button>
              </div>
            ) : deputies === null ? (
              <div className="space-y-3 border-t border-border pt-4">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="h-12 bg-muted motion-safe:animate-pulse rounded-md" />
                ))}
              </div>
            ) : (
              <>
                <p className="pb-2 text-right font-mono text-xs text-muted-foreground">
                  {t("membersCount", { count: filtered.length })}
                </p>
                {filtered.length === 0 ? (
                  <p className="border-t border-border py-12 text-center text-sm text-muted-foreground">
                    {t("noResults")}
                  </p>
                ) : (
                  <div className="border-t border-border">
                    {filtered.map((d) => (
                      <a
                        key={d.id}
                        href={`/parlamentari/${deputySlug(d.id)}`}
                        className="flex items-center gap-4 border-b border-border px-1 py-3.5 transition-colors hover:bg-muted/40"
                      >
                        <DeputyAvatar
                          photo={d.photo}
                          firstName={d.first_name}
                          lastName={d.last_name}
                          group={d.group}
                          size={40}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground">
                            {toTitleCase(`${d.first_name} ${d.last_name}`)}
                          </p>
                          {d.group && (
                            <p className="mt-0.5 flex items-center gap-2 text-sm text-muted-foreground">
                              <span
                                className="h-2 w-2 shrink-0 rounded-full"
                                style={{ backgroundColor: getGroupColor(d.group) }}
                              />
                              <span className="truncate">{groupLabel(d.group)}</span>
                            </p>
                          )}
                        </div>
                        {d.profession && (
                          <span className="hidden max-w-[15rem] truncate text-right text-sm text-muted-foreground sm:block">
                            {d.profession}
                          </span>
                        )}
                      </a>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
