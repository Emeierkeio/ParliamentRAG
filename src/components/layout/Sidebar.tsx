"use client";

import { useState, useEffect, useLayoutEffect } from "react";
import { useTranslations } from 'next-intl';
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import Image from "next/image";
import {
  MessageSquare,
  PanelLeftClose,
  PanelLeft,
  Github,
  Settings,
  Search,
  X,
  Compass,
  Menu,
  BarChart3,
  CalendarDays,
} from "lucide-react";
import { config } from "@/config";
import { SettingsModal } from "@/components/settings/SettingsModal";
import { LanguageSelector } from "@/components/layout/LanguageSelector";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  isQueryRunning?: boolean;
  isQueuing?: boolean;
  isMobile?: boolean;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

// Mobile navigation now lives in MobileBottomNav — the hamburger is retired.
// Kept as a no-op so existing page call-sites don't need touching.
export function MobileMenuButton(_props: { onClick: () => void; className?: string }) {
  return null;
}

export function Sidebar({ isCollapsed, onToggle, isQueryRunning = false, isQueuing = false, isMobile = false, isMobileOpen = false, onCloseMobile }: SidebarProps) {
  const t = useTranslations('Sidebar');
  const pathname = usePathname();
  const [infoOpen, setInfoOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  // Seed from sessionStorage so full-page navigations render the date instantly
  // (each tool switch is a full reload — without the cache the footer flashes
  // a placeholder and the whole bottom block shifts). Read in useLayoutEffect
  // (pre-paint) rather than in the useState initializer to avoid an SSR
  // hydration mismatch.
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  useLayoutEffect(() => {
    const cached = sessionStorage.getItem("lastUpdateDate");
    if (cached) setLastUpdate(cached);
  }, []);

  // Refresh in the background; update state/cache only if the value changed
  useEffect(() => {
    fetch("/api/config/last-update")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.last_update) {
          // Format YYYY-MM-DD to DD/MM/YYYY
          const [y, m, d] = data.last_update.split("-");
          const formatted = `${d}/${m}/${y}`;
          sessionStorage.setItem("lastUpdateDate", formatted);
          setLastUpdate(prev => (prev === formatted ? prev : formatted));
        }
      })
      .catch(() => {});
  }, []);

  const handleNavClick = (action: () => void) => {
    action();
    if (isMobile && onCloseMobile) {
      onCloseMobile();
    }
  };

  // When query is running or queuing, open tools in new tab to preserve state
  const navTo = (path: string) => {
    if (isQueryRunning || isQueuing) {
      window.open(path, "_blank");
    } else {
      window.location.href = path;
    }
  };

  // On mobile the bottom nav (MobileBottomNav) replaces the sidebar entirely
  if (isMobile) {
    return null;
  }

  // Desktop sidebar
  return (
    <>
      <aside
        className={cn(
          "hidden md:flex h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 ease-out",
          isCollapsed ? "w-[70px]" : "w-[260px]"
        )}
      >
        {/* Header */}
        <div className="flex h-20 items-center px-4">
          <div
            className={cn(
              "flex items-center gap-3 overflow-hidden transition-all duration-300 w-full",
              isCollapsed ? "justify-center" : "justify-between"
            )}
          >
            {/* Logo Area */}
            <div
              className={cn("flex items-center gap-3 transition-opacity duration-300 cursor-pointer", isCollapsed && "w-10 justify-center")}
              onClick={() => window.location.href = "/"}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center text-sidebar-foreground">
                <Image src="/logo.svg" alt={config.app.name} width={36} height={36} />
              </div>
              {!isCollapsed && (
                <div className="flex flex-col fade-in">
                  <span className="[font-family:var(--font-display)] text-base font-semibold tracking-tight text-sidebar-foreground">
                    {config.app.name}
                  </span>
                </div>
              )}
            </div>

             {/* Toggle Button Inside Header when Expanded */}
            {!isCollapsed && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onToggle}
                  className="h-8 w-8 text-sidebar-foreground/50 hover:bg-transparent hover:text-sidebar-foreground ml-auto"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </Button>
            )}
          </div>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 py-6 px-3">
          <nav className="flex flex-col gap-1">
            {/* Primary */}
            <NavButton
              item={{ icon: MessageSquare, label: t('topicSearch'), href: "/home", isActive: pathname === "/home", onClick: () => window.location.href = "/home" }}
              isCollapsed={isCollapsed}
              variant="primary"
              disabled={isQueryRunning}
            />

            {/* Strumenti */}
            {!isCollapsed && (
              <p className="text-[11px] uppercase tracking-[0.2em] text-sidebar-foreground/40 mt-6 mb-2 px-3">{t('tools')}</p>
            )}
            {isCollapsed && <div className="mt-4 mb-1 mx-auto w-5 border-t border-sidebar-border" />}

            <NavButton
              item={{ icon: Search, label: t('actsSearch'), href: "/search", isActive: pathname === "/search", onClick: () => navTo("/search") }}
              isCollapsed={isCollapsed}
              disabled={false}
            />

            <NavButton
              item={{ icon: BarChart3, label: t('authorityAnalysis'), href: "/ranking", isActive: pathname === "/ranking", onClick: () => navTo("/ranking") }}
              isCollapsed={isCollapsed}
              disabled={false}
            />

            <NavButton
              item={{ icon: Compass, label: t('ideologicalCompass'), href: "/compass", isActive: pathname === "/compass", onClick: () => navTo("/compass") }}
              isCollapsed={isCollapsed}
              disabled={false}
            />

            <NavButton
              item={{ icon: CalendarDays, label: t('parliamentaryTimeline'), href: "/timeline", isActive: pathname === "/timeline", onClick: () => navTo("/timeline") }}
              isCollapsed={isCollapsed}
              disabled={false}
            />

          </nav>
        </ScrollArea>

        {/* Bottom Navigation */}
        <div className="p-3 pb-5 border-t border-sidebar-border">
          <nav className="flex flex-col gap-0.5 pt-2">
            <LanguageSelector isCollapsed={isCollapsed} />
            <NavButton
                item={{ icon: Settings, label: t('settings'), onClick: () => setSettingsOpen(true) }}
                isCollapsed={isCollapsed}
            />
            <NavButton
                item={{ icon: Github, label: t('documentation'), onClick: () => window.open("https://github.com/Emeierkeio/thesis-ParliamentRAG", "_blank") }}
                isCollapsed={isCollapsed}
            />

            {/* Data date — subtle footer line. Always mounted (icon-only when
                collapsed) so the bottom stack never changes height on toggle.
                Styled tooltip (like the nav icons) carries the full label. */}
            <div className="mt-3 pt-3 border-t border-sidebar-border">
              {isCollapsed ? (
                // Collapsed: icon-only box, tooltip carries the full label
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <div className="flex items-center justify-center w-9 h-9 mx-auto text-sidebar-foreground/35 cursor-default">
                      <CalendarDays className="h-4 w-4 shrink-0" />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right" sideOffset={10} className="bg-popover text-popover-foreground border-border font-medium">
                    {`${t('dataUpdatedAt')} ${lastUpdate ?? "…"}`}
                  </TooltipContent>
                </Tooltip>
              ) : (
                // Expanded: the date is already readable — no tooltip
                <div className="flex items-center h-8 gap-2 px-3 text-[10px] uppercase tracking-wide text-sidebar-foreground/35 whitespace-nowrap overflow-hidden cursor-default">
                  <CalendarDays className="h-3 w-3 shrink-0" />
                  <span className="truncate">{t('dataShort')} <strong className="text-sidebar-foreground/55 tabular-nums font-semibold">{lastUpdate || "--/--/----"}</strong></span>
                </div>
              )}
            </div>

            {/* Expand button when collapsed - at very bottom */}
            {isCollapsed && (
              <div className="mt-4 flex justify-center pt-4 border-t border-sidebar-border">
                <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={onToggle}
                        className="h-10 w-10 text-sidebar-foreground/50 hover:text-primary transition-colors"
                    >
                        <PanelLeft className="h-5 w-5" />
                    </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right" sideOffset={10} className="bg-popover text-popover-foreground border-border font-medium">{t('expandMenu')}</TooltipContent>
                </Tooltip>
              </div>
            )}
          </nav>
        </div>
      </aside>

      {/* Info Modal */}
      <InfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />

      {/* Settings Modal */}
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

    </>
  );
}

interface NavItem {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href?: string;
  onClick?: () => void;
  isActive?: boolean;
}

interface NavButtonProps {
  item: NavItem;
  isCollapsed: boolean;
  variant?: "primary" | "default";
  disabled?: boolean;
}

function NavButton({ item, isCollapsed, variant = "default", disabled = false }: NavButtonProps) {
  const isPrimary = variant === "primary";

  const button = (
    <Button
      variant="ghost"
      disabled={disabled}
      className={cn(
        "w-full justify-start transition-all duration-200",
        // Primary: full-size nav item
        isPrimary && "gap-3 h-10 mb-1",
        // Default (strumenti): compact
        !isPrimary && "gap-2.5 h-8 mb-0.5 text-[13px]",
        // Default State
        "text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
        // Active State
        item.isActive && !isPrimary && "bg-sidebar-accent/60 text-sidebar-foreground font-medium",
        // Primary Variant - subtle highlight, no heavy box
        isPrimary && "text-sidebar-foreground font-semibold hover:bg-sidebar-accent/50",
        isPrimary && item.isActive && "bg-sidebar-accent/40",
        // Collapsed Logic
        isCollapsed && "justify-center px-0 mx-auto",
        isCollapsed && isPrimary && "w-10 h-10",
        isCollapsed && !isPrimary && "w-9 h-9",
        // Disabled State
        disabled && "opacity-40 pointer-events-none"
      )}
      onClick={item.onClick}
    >
      <item.icon className={cn(
        "shrink-0",
        isPrimary ? "h-5 w-5 text-sidebar-foreground" : "h-4 w-4 text-current"
      )} />
      {!isCollapsed && (
        <span className="truncate">{item.label}</span>
      )}
    </Button>
  );

  if (isCollapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="right" sideOffset={10} className="bg-popover text-popover-foreground border-border font-medium">
          {item.label}
        </TooltipContent>
      </Tooltip>
    );
  }

  return button;
}

// Info Modal
function InfoModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Image src="/logo.svg" alt="" width={24} height={24} />
            {config.app.name}
          </DialogTitle>
          <DialogDescription>
            Versione {config.app.version}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Sistema RAG innovativo per l&apos;analisi bilanciata dei dibattiti parlamentari italiani.
            Fornisce risposte che rappresentano tutte le forze politiche presenti in Parlamento.
          </p>

          <Separator />

          <div className="space-y-2">
            <h4 className="text-sm font-medium">Caratteristiche principali</h4>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Analisi bilanciata maggioranza/opposizione</li>
              <li>• Identificazione automatica degli esperti per tema</li>
              <li>• Citazioni verificabili dagli interventi parlamentari</li>
              <li>• Metriche di bilanciamento politico</li>
            </ul>
          </div>

          <Separator />

          <div className="space-y-2">
            <h4 className="text-sm font-medium">Tecnologie</h4>
            <div className="flex flex-wrap gap-2">
              {["Next.js", "FastAPI", "Neo4j", "OpenAI", "LangChain"].map((tech) => (
                <span
                  key={tech}
                  className="px-2 py-1 text-xs bg-muted rounded-md text-muted-foreground"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>

          <Separator />

          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Dati aggiornati al:</span>
            <span className="font-medium">4 febbraio 2026</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

