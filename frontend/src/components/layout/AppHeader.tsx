"use client";

import { useState } from "react";
import Image from "next/image";
import { usePathname, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Search, Settings, Globe, ChevronDown, Check } from "lucide-react";
import { SettingsModal } from "@/components/settings/SettingsModal";
import { openCommandPalette } from "@/components/shared/CommandPalette";
import { LOCALES } from "@/components/layout/LanguageSelector";

/**
 * Shell dell'applicazione: barra superiore leggera al posto della sidebar.
 * La navigazione parla di entità del Parlamento, non di strumenti
 * (RADICAL_REDESIGN.md §3-4). Su mobile la primaria è la bottom nav:
 * qui resta solo la riga wordmark + ricerca.
 */
export function AppHeader() {
  const t = useTranslations("Sidebar");
  const pathname = usePathname();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const exploreItems = [
    { label: t("deputies"), href: "/parlamentari" },
    { label: t("groups"), href: "/gruppi" },
    { label: t("acts"), href: "/atti" },
    { label: t("sessions"), href: "/sedute" },
  ];
  const analyzeItems = [
    { label: t("ideologicalCompass"), href: "/compass" },
    { label: t("authorityAnalysis"), href: "/ranking" },
  ];
  const isExplore = exploreItems.some((i) => pathname.startsWith(i.href)) || pathname.startsWith("/search");
  const isAnalyze = analyzeItems.some((i) => pathname.startsWith(i.href));

  const linkClass = (active: boolean) =>
    cn(
      "inline-flex items-center gap-1 px-2.5 h-8 rounded-md text-[13px] transition-colors",
      active
        ? "text-foreground font-medium bg-accent"
        : "text-muted-foreground hover:text-foreground hover:bg-accent/60"
    );

  return (
    <>
      <header className="sticky top-0 z-40 shrink-0 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="flex h-14 items-center gap-2 px-4 sm:px-6">
          {/* Brand */}
          <a href="/home" className="flex items-center gap-2.5 shrink-0 mr-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm">
            <Image src="/logo-blue.svg" alt="" width={30} height={21} />
            <span className="[font-family:var(--font-display)] text-[17px] font-semibold tracking-tight hidden sm:inline">
              ParliamentRAG
            </span>
          </a>

          {/* Nav: solo desktop — su mobile c'è la bottom nav */}
          <nav className="hidden md:flex items-center gap-0.5" aria-label={t("explore")}>
            <a href="/home" className={linkClass(pathname === "/home" || pathname.startsWith("/chat"))}>
              {t("navTopic")}
            </a>

            <NavMenu label={t("explore")} active={isExplore} items={[...exploreItems, { label: t("actsSearch"), href: "/search" }]} />
            <NavMenu label={t("analyze")} active={isAnalyze} items={analyzeItems} />

            <a href="/data" className={linkClass(pathname === "/data")}>
              {t("openData")}
            </a>
            <a href="/metodologia" className={linkClass(pathname === "/metodologia")}>
              {t("methodology")}
            </a>
          </nav>

          {/* Azioni a destra */}
          <div className="flex items-center gap-1 ml-auto">
            <button
              onClick={() => openCommandPalette()}
              className="inline-flex items-center gap-2 h-8 px-2.5 rounded-md border border-border text-[13px] text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors"
            >
              <Search className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden lg:inline">{t("commandPalette")}</span>
              <kbd className="hidden md:inline font-mono text-[10px] border border-border rounded px-1">⌘K</kbd>
            </button>
            <LanguageMenu />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSettingsOpen(true)}
              aria-label={t("settings")}
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}

function NavMenu({
  label,
  active,
  items,
}: {
  label: string;
  active: boolean;
  items: { label: string; href: string }[];
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "inline-flex items-center gap-1 px-2.5 h-8 rounded-md text-[13px] transition-colors",
            active
              ? "text-foreground font-medium bg-accent"
              : "text-muted-foreground hover:text-foreground hover:bg-accent/60"
          )}
          aria-expanded={open}
        >
          {label}
          <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" sideOffset={6} className="w-52 p-1.5">
        <ul>
          {items.map((item) => (
            <li key={item.href}>
              <a
                href={item.href}
                className={cn(
                  "flex items-center px-2.5 py-2 rounded-md text-[13px] transition-colors",
                  pathname.startsWith(item.href)
                    ? "text-foreground font-medium bg-accent"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/60"
                )}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

function LanguageMenu() {
  const locale = useLocale();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [open, setOpen] = useState(false);

  const switchTo = (nextLocale: string) => {
    if (nextLocale === locale) return;
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; SameSite=Lax`;
    const params = new URLSearchParams(searchParams.toString());
    if (nextLocale === "it") params.delete("lang");
    else params.set("lang", nextLocale);
    const qs = params.toString();
    window.location.href = `${pathname}${qs ? `?${qs}` : ""}`;
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className="inline-flex items-center gap-1 h-8 px-2 rounded-md text-[13px] text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors"
          aria-label={locale.toUpperCase()}
        >
          <Globe className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="font-mono text-[11px] uppercase">{locale}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" sideOffset={6} className="w-44 p-1.5">
        <ul>
          {LOCALES.map((l) => (
            <li key={l.code}>
              <button
                onClick={() => switchTo(l.code)}
                className={cn(
                  "flex w-full items-center gap-2 px-2.5 py-2 rounded-md text-[13px] transition-colors",
                  l.code === locale
                    ? "text-foreground font-medium bg-accent"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/60"
                )}
              >
                {l.code === locale && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
                <span className={cn(l.code !== locale && "pl-[22px]")}>{l.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
