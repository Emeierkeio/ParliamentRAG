"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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
  GraduationCap,
  BookOpen,
  Building2,
  BarChart3,
  Users,
} from "lucide-react";
import { config } from "@/config";
import { SettingsModal } from "@/components/settings/SettingsModal";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  isQueryRunning?: boolean;
  isQueuing?: boolean;
  isMobile?: boolean;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function MobileMenuButton({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onClick}
      className={cn("md:hidden h-10 w-10 shrink-0", className)}
    >
      <Menu className="h-5 w-5" />
    </Button>
  );
}

export function Sidebar({ isCollapsed, onToggle, isQueryRunning = false, isQueuing = false, isMobile = false, isMobileOpen = false, onCloseMobile }: SidebarProps) {
  const pathname = usePathname();
  const [infoOpen, setInfoOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleNavClick = (action: () => void) => {
    action();
    if (isMobile && onCloseMobile) {
      onCloseMobile();
    }
  };

  // When queuing, open tools in new tab to preserve queue position
  const navTo = (path: string) => {
    if (isQueuing) {
      window.open(path, "_blank");
    } else {
      window.location.href = path;
    }
  };

  // On mobile, render as overlay
  if (isMobile) {
    return (
      <>
        {/* Backdrop */}
        {isMobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
          />
        )}

        {/* Slide-in sidebar */}
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 ease-out",
            isMobileOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          {/* Header */}
          <div className="flex h-16 items-center justify-between px-4">
            <div
              className="flex items-center gap-3 cursor-pointer"
              onClick={() => handleNavClick(() => { window.location.href = "/"; })}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center text-sidebar-foreground">
                <Image src="/logo.svg" alt={config.app.name} width={36} height={36} />
              </div>
              <span className="text-sm font-bold tracking-tight text-sidebar-foreground">
                {config.app.name}
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onCloseMobile}
              className="h-8 w-8 text-sidebar-foreground/50 hover:text-sidebar-foreground"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Navigation */}
          <ScrollArea className="flex-1 py-4 px-3">
            <nav className="flex flex-col gap-1">
              {/* Primary */}
              <NavButton
                item={{ icon: MessageSquare, label: "Ricerca Topic", isActive: pathname === "/", onClick: () => handleNavClick(() => { window.location.href = "/"; }) }}
                isCollapsed={false}
                variant="primary"
                disabled={isQueryRunning}
              />

              {/* Strumenti */}
              <p className="text-[10px] font-medium uppercase tracking-widest text-sidebar-foreground/30 mt-6 mb-2 px-3">Strumenti</p>
              <NavButton
                item={{ icon: Search, label: "Ricerca Atti", isActive: pathname === "/search", onClick: () => handleNavClick(() => navTo("/search")) }}
                isCollapsed={false}
                disabled={isQueryRunning && !isQueuing}
              />
              <NavButton
                item={{ icon: BarChart3, label: "Analisi Autorità", isActive: pathname === "/ranking", onClick: () => handleNavClick(() => navTo("/ranking")) }}
                isCollapsed={false}
                disabled={isQueryRunning && !isQueuing}
              />
              <NavButton
                item={{ icon: Compass, label: "Compasso Ideologico", isActive: pathname === "/compass", onClick: () => handleNavClick(() => navTo("/compass")) }}
                isCollapsed={false}
                disabled={isQueryRunning && !isQueuing}
              />

            </nav>
          </ScrollArea>

          {/* Bottom */}
          <div className="p-3 pb-6">
            <NavButton
              item={{ icon: Settings, label: "Impostazioni", onClick: () => handleNavClick(() => setSettingsOpen(true)) }}
              isCollapsed={false}
            />
            <NavButton
              item={{ icon: Github, label: "Documentazione", onClick: () => window.open("https://github.com/Emeierkeio/thesis-ParliamentRAG", "_blank") }}
              isCollapsed={false}
            />
            <CreditsRow isCollapsed={false} />
          </div>
        </aside>

        {/* Modals */}
        <InfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />
        <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      </>
    );
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
                  <span className="text-sm font-bold tracking-tight text-sidebar-foreground">
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
              item={{ icon: MessageSquare, label: "Ricerca Topic", href: "/", isActive: pathname === "/", onClick: () => window.location.href = "/" }}
              isCollapsed={isCollapsed}
              variant="primary"
              disabled={isQueryRunning}
            />

            {/* Strumenti */}
            {!isCollapsed && (
              <p className="text-[10px] font-medium uppercase tracking-widest text-sidebar-foreground/30 mt-6 mb-2 px-3">Strumenti</p>
            )}
            {isCollapsed && <div className="mt-4 mb-1 mx-auto w-5 border-t border-sidebar-border" />}

            <NavButton
              item={{ icon: Search, label: "Ricerca Atti", href: "/search", isActive: pathname === "/search", onClick: () => navTo("/search") }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning && !isQueuing}
            />

            <NavButton
              item={{ icon: BarChart3, label: "Analisi Autorità", href: "/ranking", isActive: pathname === "/ranking", onClick: () => navTo("/ranking") }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning && !isQueuing}
            />

            <NavButton
              item={{ icon: Compass, label: "Compasso Ideologico", href: "/compass", isActive: pathname === "/compass", onClick: () => navTo("/compass") }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning && !isQueuing}
            />

          </nav>
        </ScrollArea>

        {/* Bottom Navigation */}
        <div className="p-3 pb-6">
          <nav className="flex flex-col gap-1">
            <NavButton
                item={{ icon: Settings, label: "Impostazioni", onClick: () => setSettingsOpen(true) }}
                isCollapsed={isCollapsed}
            />
            <NavButton
                item={{ icon: Github, label: "Documentazione", onClick: () => window.open("https://github.com/Emeierkeio/thesis-ParliamentRAG", "_blank") }}
                isCollapsed={isCollapsed}
            />

            {/* Credits */}
            <CreditsRow isCollapsed={isCollapsed} />

            {/* Expand button when collapsed - at very bottom */}
            {isCollapsed && (
              <div className="mt-4 flex justify-center pt-4 border-t border-sidebar-border">
                <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={onToggle}
                        className="h-10 w-10 text-sidebar-foreground/50 hover:text-sidebar-foreground transition-colors"
                    >
                        <PanelLeft className="h-5 w-5" />
                    </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right">Espandi menu</TooltipContent>
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

function CreditsRow({ isCollapsed }: { isCollapsed: boolean }) {
  const content = (
    <div className="space-y-3 text-sm">
      <div className="flex items-center gap-2">
        <GraduationCap className="h-4 w-4 text-primary" />
        <span className="font-medium">Tesi di Laurea Magistrale</span>
      </div>
      <p className="text-muted-foreground text-xs leading-relaxed">
        Sistema RAG per l&apos;analisi bilanciata dei dibattiti parlamentari italiani.
      </p>
      <Separator />
      <div className="space-y-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <BookOpen className="h-3.5 w-3.5" />
          <span>Autore: <strong className="text-foreground">Mirko Tritella</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <Building2 className="h-3.5 w-3.5" />
          <span>Università degli Studi di Milano Bicocca</span>
        </div>
        <div className="flex items-center gap-2">
          <Users className="h-3.5 w-3.5" />
          <span>Relatore: Prof. Matteo <strong className="text-foreground">Palmonari</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <Users className="h-3.5 w-3.5" />
          <span>Correlatore: Dott. Riccardo <strong className="text-foreground">Pozzi</strong></span>
        </div>
      </div>
    </div>
  );

  if (isCollapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            className="w-9 h-9 justify-center px-0 mx-auto text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
          >
            <GraduationCap className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right" sideOffset={10} className="max-w-[260px] p-3">
          {content}
        </TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2.5 h-8 mb-0.5 text-[13px] text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
        >
          <GraduationCap className="h-4 w-4 shrink-0" />
          <span className="truncate">Crediti</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="w-[260px] p-4">
        {content}
      </PopoverContent>
    </Popover>
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
            <span className="font-medium">Gennaio 2025</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

