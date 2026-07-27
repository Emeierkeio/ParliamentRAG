"use client";

import { useState, useEffect, useLayoutEffect } from "react";
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
  // Tab switches are full page loads: without instant feedback the app feels
  // dead for the whole transition. The overlay stays up until the new
  // document paints; pageshow clears it when iOS restores from bfcache.
  const [navTarget, setNavTarget] = useState<string | null>(null);
  useEffect(() => {
    const clear = () => setNavTarget(null);
    window.addEventListener("pageshow", clear);
    return () => window.removeEventListener("pageshow", clear);
  }, []);

  const isVisible = VISIBLE_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
  if (!isVisible) return null;

  const tabClass = (isActive: boolean) =>
    cn(
      "flex flex-1 min-w-0 flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors",
      isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
    );

  // Active tab: primary colour + a light spring on the icon, no pill —
  // quieter than a grey blob on the glass bar
  const iconClass = (isActive: boolean) =>
    cn(
      "h-[19px] w-[19px] transition-transform duration-300 ease-out mb-0.5",
      isActive && "scale-110 -translate-y-px"
    );

  return (
    <>
    <nav
      className="md:hidden fixed inset-x-3 bottom-[calc(0.625rem+env(safe-area-inset-bottom))] z-40 rounded-[1.75rem] border border-white/50 bg-background/60 backdrop-blur-2xl backdrop-saturate-150 shadow-[0_8px_32px_rgba(27,58,92,0.16)]"
      aria-label={t("tools")}
    >
      <div className="flex h-14 items-stretch justify-around px-1">
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
              className={tabClass(isActive || navTarget === href)}
              onClick={() => {
                if (!isActive) setNavTarget(href);
              }}
            >
              <Icon className={iconClass(isActive)} />
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
              <Menu className={iconClass(moreOpen)} />
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

    {/* Slim indeterminate progress bar (YouTube-style) while the next
        document loads. Lives OUTSIDE the nav: its backdrop-filter makes the
        nav a containing block for fixed descendants, which would pin the bar
        to the nav instead of the viewport. */}
    {navTarget && (
      <div className="md:hidden fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden" role="progressbar" aria-label={t("tools")}>
        <div className="h-full w-1/3 bg-primary motion-safe:animate-[nav-progress_1s_ease-in-out_infinite]" />
      </div>
    )}
    </>
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
    <div className="px-5 pt-5">
      {/* Radix requires a title for screen readers; visually the sheet
          starts straight from the language section */}
      <SheetTitle className="sr-only">{config.app.name}</SheetTitle>

      {/* Language — the label keeps clear of the sheet's absolute close X
          (top-right), and the extra margin drops the grid below it */}
      <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-3 pr-10">
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

      {/* Secondary actions — icon-only, one row */}
      <div className="mt-3 grid grid-cols-2 gap-1.5">
        <button
          onClick={onOpenSettings}
          aria-label={t("settings")}
          className="flex h-10 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted/50 transition-colors"
        >
          <Settings className="h-4 w-4" />
        </button>
        <a
          href="https://github.com/Emeierkeio/ParliamentRAG"
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t("documentation")}
          className="flex h-10 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted/50 transition-colors"
        >
          <Github className="h-4 w-4" />
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
