"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { MessageSquare, Search, BarChart3, Compass } from "lucide-react";

const NAV_ITEMS = [
  { href: "/home", icon: MessageSquare, key: "navTopic" },
  { href: "/search", icon: Search, key: "navActs" },
  { href: "/ranking", icon: BarChart3, key: "navAuthority" },
  { href: "/compass", icon: Compass, key: "navCompass" },
] as const;

// App pages only — the landing ("/") keeps its own editorial masthead
const VISIBLE_PREFIXES = ["/home", "/search", "/ranking", "/compass", "/chat"];

/**
 * Fixed bottom navigation bar for mobile (hidden ≥md, where the sidebar
 * takes over). Pages that show it reserve space via pb-[calc(3.5rem+...)].
 */
export function MobileBottomNav() {
  const t = useTranslations("Sidebar");
  const pathname = usePathname();

  const isVisible = VISIBLE_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
  if (!isVisible) return null;

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
              className={cn(
                "flex flex-1 min-w-0 flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors",
                isActive
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-12 items-center justify-center rounded-full transition-colors",
                  isActive && "bg-primary/10"
                )}
              >
                <Icon className="h-[18px] w-[18px]" />
              </span>
              <span className="truncate max-w-full px-1">
                {t(key as "navTopic")}
              </span>
            </a>
          );
        })}
      </div>
    </nav>
  );
}
