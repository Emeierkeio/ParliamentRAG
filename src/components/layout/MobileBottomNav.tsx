"use client";

import { useState, useEffect, useLayoutEffect } from "react";
import Image from "next/image";
import { usePathname, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import {
  MessageSquare,
  Search,
  BarChart3,
  Compass,
  Menu,
  Github,
  Settings,
  CalendarDays,
  Check,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { SettingsModal } from "@/components/settings/SettingsModal";
import { LOCALES } from "@/components/layout/LanguageSelector";
import { config } from "@/config";

const NAV_ITEMS = [
  { href: "/home", icon: MessageSquare, key: "navTopic" },
  { href: "/search", icon: Search, key: "navActs" },
  { href: "/ranking", icon: BarChart3, key: "navAuthority" },
  { href: "/compass", icon: Compass, key: "navCompass" },
  { href: "/timeline", icon: CalendarDays, key: "navTimeline" },
] as const;

// App pages only — the landing ("/") keeps its own editorial masthead
const VISIBLE_PREFIXES = [
  "/home",
  "/search",
  "/ranking",
  "/compass",
  "/timeline",
  "/chat",
  "/explorer",
  "/valutazione",
];

/**
 * Fixed bottom navigation bar for mobile (hidden ≥md, where the sidebar
 * takes over). Replaces the mobile drawer entirely: the fifth "more" tab
 * opens a bottom sheet with the secondary items (language, settings,
 * documentation, data-update date). Pages that show it reserve space via
 * pb-[calc(3.5rem+...)].
 */
export function MobileBottomNav() {
  const t = useTranslations("Sidebar");
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const isVisible = VISIBLE_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
  if (!isVisible) return null;

  const tabClass = (isActive: boolean) =>
    cn(
      "flex flex-1 min-w-0 flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors",
      isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
    );

  const pillClass = (isActive: boolean) =>
    cn(
      "flex h-6 w-12 items-center justify-center rounded-full transition-colors",
      isActive && "bg-primary/10"
    );

  return (
    <nav
      className="md:hidden fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/90 backdrop-blur-lg pb-[env(safe-area-inset-bottom)]"
      aria-label={t("tools")}
    >
      <div className="flex h-14 items-stretch justify-around">
        {NAV_ITEMS.map(({ href, icon: Icon, key }) => {
          const isActive =
            href === "/home"
              ? pathname === "/home" || pathname.startsWith("/chat")
              : pathname.startsWith(href);
          return (
            <a
              key={href}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={tabClass(isActive)}
            >
              <span className={pillClass(isActive)}>
                <Icon className="h-[18px] w-[18px]" />
              </span>
              <span className="truncate max-w-full px-1">
                {t(key as "navTopic")}
              </span>
            </a>
          );
        })}

        {/* More: secondary items previously in the mobile drawer */}
        <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
          <SheetTrigger asChild>
            <button className={tabClass(moreOpen)}>
              <span className={pillClass(moreOpen)}>
                <Menu className="h-[18px] w-[18px]" />
              </span>
              <span className="truncate max-w-full px-1">{t("navMore")}</span>
            </button>
          </SheetTrigger>
          <SheetContent
            side="bottom"
            className="rounded-t-2xl border-t border-border pb-[calc(1rem+env(safe-area-inset-bottom))]"
          >
            <MoreSheetContent
              onOpenSettings={() => {
                setMoreOpen(false);
                setSettingsOpen(true);
              }}
            />
          </SheetContent>
        </Sheet>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </nav>
  );
}

function MoreSheetContent({ onOpenSettings }: { onOpenSettings: () => void }) {
  const t = useTranslations("Sidebar");
  const tLang = useTranslations("LanguageSelector");
  const locale = useLocale();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Data-update date: same sessionStorage-seeded fetch as the desktop sidebar
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  useLayoutEffect(() => {
    const cached = sessionStorage.getItem("lastUpdateDate");
    if (cached) setLastUpdate(cached);
  }, []);
  useEffect(() => {
    fetch("/api/config/last-update")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.last_update) {
          const [y, m, d] = data.last_update.split("-");
          const formatted = `${d}/${m}/${y}`;
          sessionStorage.setItem("lastUpdateDate", formatted);
          setLastUpdate((prev) => (prev === formatted ? prev : formatted));
        }
      })
      .catch(() => {});
  }, []);

  const switchTo = (nextLocale: string) => {
    if (nextLocale === locale) return;
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; SameSite=Lax`;
    const params = new URLSearchParams(searchParams.toString());
    if (nextLocale === "it") {
      params.delete("lang");
    } else {
      params.set("lang", nextLocale);
    }
    const qs = params.toString();
    window.location.href = `${pathname}${qs ? `?${qs}` : ""}`;
  };

  return (
    <div className="px-1">
      <SheetHeader className="px-0 pb-2">
        <SheetTitle asChild>
          <a href="/" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center bg-primary rounded-md">
              <Image src="/logo.svg" alt="" width={22} height={22} />
            </span>
            <span className="[font-family:var(--font-display)] text-lg font-semibold tracking-tight">
              {config.app.name}
            </span>
          </a>
        </SheetTitle>
      </SheetHeader>

      {/* Language */}
      <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-3 mb-2">
        {tLang("switchTo")}
      </p>
      <div className="grid grid-cols-3 gap-1.5">
        {LOCALES.map((l) => (
          <button
            key={l.code}
            onClick={() => switchTo(l.code)}
            className={cn(
              "flex items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[13px] transition-colors",
              l.code === locale
                ? "border-primary/40 bg-primary/5 text-primary font-medium"
                : "border-border text-muted-foreground hover:bg-muted/50"
            )}
          >
            {l.code === locale && <Check className="h-3.5 w-3.5 shrink-0" />}
            <span className="truncate">{l.label}</span>
          </button>
        ))}
      </div>

      {/* Secondary actions */}
      <div className="mt-4 flex flex-col gap-0.5">
        <button
          onClick={onOpenSettings}
          className="flex items-center gap-3 rounded-lg px-2 py-2.5 text-sm text-foreground/80 hover:bg-muted/50 transition-colors"
        >
          <Settings className="h-4 w-4 text-muted-foreground" />
          {t("settings")}
        </button>
        <a
          href="https://github.com/Emeierkeio/thesis-ParliamentRAG"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 rounded-lg px-2 py-2.5 text-sm text-foreground/80 hover:bg-muted/50 transition-colors"
        >
          <Github className="h-4 w-4 text-muted-foreground" />
          {t("documentation")}
        </a>
      </div>

      {/* Data date */}
      <div className="mt-3 pt-3 border-t border-border/60 flex items-center gap-2 px-2 text-[10px] uppercase tracking-wide text-muted-foreground/70">
        <CalendarDays className="h-3 w-3 shrink-0" />
        <span className="truncate">
          {t("dataShort")}{" "}
          <strong className="tabular-nums font-semibold text-muted-foreground">
            {lastUpdate || "--/--/----"}
          </strong>
        </span>
      </div>
    </div>
  );
}
