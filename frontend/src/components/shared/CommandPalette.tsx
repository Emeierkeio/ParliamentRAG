"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  MessageSquare,
  FileText,
  CalendarDays,
  Network,
  BarChart3,
  Compass,
  Database,
  User,
} from "lucide-react";
import { config, getGroupAbbrev } from "@/config";
import { getTopics } from "@/lib/constants";

interface DeputyHit {
  id: string;
  first_name: string;
  last_name: string;
  group?: string;
}

/**
 * Ricerca globale (Cmd/Ctrl+K): navigazione, temi suggeriti e deputati.
 * I deputati arrivano da /search/deputies (endpoint esistente, nessuna
 * modifica backend). La selezione naviga con full page load, coerente con
 * il resto dell'app.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("CommandPalette");
  const tSidebar = useTranslations("Sidebar");
  const locale = useLocale();
  const [query, setQuery] = useState("");
  const [deputies, setDeputies] = useState<DeputyHit[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setDeputies([]);
    }
  }, [open]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (q.length < 2) {
      setDeputies([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${config.api.baseUrl}/search/deputies?q=${encodeURIComponent(q)}`
        );
        if (!res.ok) return;
        const data = await res.json();
        const list: DeputyHit[] = Array.isArray(data) ? data : data.deputies ?? [];
        setDeputies(list.slice(0, 5));
      } catch {
        // ricerca best-effort: in errore la sezione deputati resta vuota
      }
    }, 200);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const go = useCallback((path: string) => {
    onOpenChange(false);
    window.location.href = path;
  }, [onOpenChange]);

  const navItems = [
    { icon: MessageSquare, label: tSidebar("topicSearch"), path: "/home" },
    { icon: FileText, label: tSidebar("actsSearch"), path: "/search" },
    { icon: CalendarDays, label: tSidebar("parliamentaryTimeline"), path: "/timeline" },
    { icon: Network, label: tSidebar("graphExplorer"), path: "/explorer" },
    { icon: BarChart3, label: tSidebar("authorityAnalysis"), path: "/ranking" },
    { icon: Compass, label: tSidebar("ideologicalCompass"), path: "/compass" },
    { icon: Database, label: tSidebar("openData"), path: "/data" },
  ];

  const topics = getTopics(locale).slice(0, 6);
  const trimmed = query.trim();

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("title")}
      description={t("description")}
    >
      <CommandInput
        placeholder={t("placeholder")}
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>{t("noResults")}</CommandEmpty>

        {trimmed.length >= 3 && (
          <CommandGroup heading={t("ask")}>
            <CommandItem
              value={`ask-${trimmed}`}
              onSelect={() => go(`/home?q=${encodeURIComponent(trimmed)}`)}
            >
              <MessageSquare aria-hidden="true" />
              <span>{t("askAbout", { query: trimmed })}</span>
            </CommandItem>
          </CommandGroup>
        )}

        {deputies.length > 0 && (
          <CommandGroup heading={t("deputies")}>
            {deputies.map((d) => (
              <CommandItem
                key={d.id}
                value={`dep-${d.first_name} ${d.last_name}`}
                onSelect={() =>
                  go(`/search?q=${encodeURIComponent(`${d.first_name} ${d.last_name}`)}`)
                }
              >
                <User aria-hidden="true" />
                <span>
                  {d.first_name} {d.last_name}
                </span>
                {d.group && (
                  <span className="ml-auto text-xs text-muted-foreground">
                    {getGroupAbbrev(d.group)}
                  </span>
                )}
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        <CommandGroup heading={t("topics")}>
          {topics.map((topic) => (
            <CommandItem
              key={topic}
              value={`topic-${topic}`}
              onSelect={() => go(`/home?q=${encodeURIComponent(topic)}`)}
            >
              <MessageSquare aria-hidden="true" />
              <span>{topic}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading={t("navigate")}>
          {navItems.map((item) => (
            <CommandItem
              key={item.path}
              value={`nav-${item.label}`}
              onSelect={() => go(item.path)}
            >
              <item.icon aria-hidden="true" />
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

export const OPEN_COMMAND_PALETTE_EVENT = "parliamentrag:open-command-palette";

/**
 * Montata una volta nel layout: apre la palette con Cmd/Ctrl+K o con
 * l'evento custom lanciato dai bottoni di trigger (sidebar, mobile nav).
 */
export function GlobalCommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    const openFromEvent = () => setOpen(true);
    document.addEventListener("keydown", down);
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, openFromEvent);
    return () => {
      document.removeEventListener("keydown", down);
      window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, openFromEvent);
    };
  }, []);

  return <CommandPalette open={open} onOpenChange={setOpen} />;
}

export function openCommandPalette() {
  window.dispatchEvent(new CustomEvent(OPEN_COMMAND_PALETTE_EVENT));
}
