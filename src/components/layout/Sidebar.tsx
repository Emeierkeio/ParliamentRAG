"use client";

import { useState, useEffect } from "react";
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
  History,
  Github,
  Network,
  Settings,
  Trash2,
  Check,
  Search,
  X,
  ClipboardCheck,
  Menu,
  GraduationCap,
  BookOpen,
  Building2,
  BarChart3,
  Loader2,
  MessageCircle,
  Clock,
  Inbox,
  AlertCircle,
} from "lucide-react";
import { config } from "@/config";
import { SettingsModal } from "@/components/settings/SettingsModal";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  onNewChat?: () => void;
  onLoadChat?: (chat: any) => void;
  isQueryRunning?: boolean;
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

export function Sidebar({ isCollapsed, onToggle, onNewChat, onLoadChat, isQueryRunning = false, isMobile = false, isMobileOpen = false, onCloseMobile }: SidebarProps) {
  const [infoOpen, setInfoOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleNavClick = (action: () => void) => {
    action();
    if (isMobile && onCloseMobile) {
      onCloseMobile();
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
              <NavButton
                item={{ icon: MessageSquare, label: "Chat", onClick: () => handleNavClick(() => { window.location.href = "/"; }) }}
                isCollapsed={false}
                disabled={isQueryRunning}
              />
              <NavButton
                item={{ icon: Search, label: "Ricerca Atti", onClick: () => handleNavClick(() => { window.location.href = "/search"; }) }}
                isCollapsed={false}
                disabled={isQueryRunning}
              />
              <NavButton
                item={{ icon: BarChart3, label: "Ranking Autorità", onClick: () => handleNavClick(() => { window.location.href = "/ranking"; }) }}
                isCollapsed={false}
                disabled={isQueryRunning}
              />
              <NavButton
                item={{ icon: Network, label: "Esplora Grafo", onClick: () => handleNavClick(() => { window.location.href = "/explorer"; }) }}
                isCollapsed={false}
                disabled={isQueryRunning}
              />
              <NavButton
                item={{ icon: ClipboardCheck, label: "Valutazione", onClick: () => handleNavClick(() => { window.location.href = "/valutazione"; }) }}
                isCollapsed={false}
                disabled={isQueryRunning}
              />
            </nav>
          </ScrollArea>

          {/* Bottom */}
          <div className="p-3 pb-6">
            <NavButton
              item={{ icon: History, label: "Cronologia", onClick: () => handleNavClick(() => setHistoryOpen(true)) }}
              isCollapsed={false}
              disabled={isQueryRunning}
            />
            <NavButton
              item={{ icon: Settings, label: "Impostazioni", onClick: () => handleNavClick(() => setSettingsOpen(true)) }}
              isCollapsed={false}
            />
            <NavButton
              item={{ icon: Github, label: "Documentazione", onClick: () => window.open("https://github.com/Emeierkeio/thesis-ParliamentRAG", "_blank") }}
              isCollapsed={false}
            />
            <div className="mt-3 pt-3 border-t border-sidebar-border">
              <div className="rounded-xl bg-sidebar-accent/30 border border-sidebar-border/50 p-3.5 space-y-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent">
                    <GraduationCap className="h-3.5 w-3.5 text-sidebar-foreground" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[11px] font-semibold text-sidebar-foreground leading-tight">Mirko Tritella</span>
                    <span className="text-[9px] text-sidebar-foreground/60 leading-tight">A.A. 2025/2026</span>
                  </div>
                </div>

                <div className="flex items-start gap-2 pl-0.5">
                  <BookOpen className="h-3 w-3 text-sidebar-foreground/50 mt-[3px] shrink-0" />
                  <p className="text-[10px] text-sidebar-foreground/70 leading-[1.5]">
                    Tesi di Laurea Magistrale
                    <br />in Data Science
                  </p>
                </div>

                <div className="space-y-1 pl-0.5">
                  <div className="flex items-center gap-1.5">
                    <div className="h-px w-2 bg-sidebar-foreground/20" />
                    <p className="text-[9px] text-sidebar-foreground/55">Rel. Prof. M. Palmonari</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="h-px w-2 bg-sidebar-foreground/20" />
                    <p className="text-[9px] text-sidebar-foreground/55">Corr. Dott. R. Pozzi</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1 border-t border-sidebar-border/30">
                  <Building2 className="h-3 w-3 text-sidebar-foreground/40 shrink-0" />
                  <p className="text-[9px] text-sidebar-foreground/45 leading-tight">
                    Univ. degli Studi di Milano-Bicocca
                  </p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Modals */}
        <InfoModal open={infoOpen} onClose={() => setInfoOpen(false)} />
        <HistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} onLoadChat={onLoadChat} />
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
          <nav className="flex flex-col gap-2">
            <NavButton
              item={{ icon: MessageSquare, label: "Chat", href: "/", onClick: () => window.location.href = "/" }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />

            <NavButton
              item={{ icon: Search, label: "Ricerca Atti", href: "/search", onClick: () => window.location.href = "/search" }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />

            <NavButton
              item={{ icon: BarChart3, label: "Ranking Autorità", href: "/ranking", onClick: () => window.location.href = "/ranking" }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />

            <NavButton
              item={{ icon: Network, label: "Esplora Grafo", href: "/explorer", onClick: () => window.location.href = "/explorer" }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />

            <NavButton
              item={{ icon: ClipboardCheck, label: "Valutazione", onClick: () => window.location.href = "/valutazione" }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />
          </nav>
        </ScrollArea>

        {/* Bottom Navigation */}
        <div className="p-3 pb-6">
          <nav className="flex flex-col gap-1">
            <NavButton
                item={{ icon: History, label: "Cronologia", onClick: () => setHistoryOpen(true) }}
                isCollapsed={isCollapsed}
                disabled={isQueryRunning}
            />
            <NavButton
                item={{ icon: Settings, label: "Impostazioni", onClick: () => setSettingsOpen(true) }}
                isCollapsed={isCollapsed}
            />
            <NavButton
                item={{ icon: Github, label: "Documentazione", onClick: () => window.open("https://github.com/Emeierkeio/thesis-ParliamentRAG", "_blank") }}
                isCollapsed={isCollapsed}
            />

            {/* Credits */}
            {!isCollapsed && (
              <div className="mt-3 pt-3 border-t border-sidebar-border">
                <div className="rounded-xl bg-sidebar-accent/30 border border-sidebar-border/50 p-3.5 space-y-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent">
                      <GraduationCap className="h-3.5 w-3.5 text-sidebar-foreground" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[11px] font-semibold text-sidebar-foreground leading-tight">Mirko Tritella</span>
                      <span className="text-[9px] text-sidebar-foreground/60 leading-tight">A.A. 2025/2026</span>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 pl-0.5">
                    <BookOpen className="h-3 w-3 text-sidebar-foreground/50 mt-[3px] shrink-0" />
                    <p className="text-[10px] text-sidebar-foreground/70 leading-[1.5]">
                      Tesi di Laurea Magistrale
                      <br />in Data Science
                    </p>
                  </div>

                  <div className="space-y-1 pl-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-px w-2 bg-sidebar-foreground/20" />
                      <p className="text-[9px] text-sidebar-foreground/55">Rel. Prof. M. Palmonari</p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className="h-px w-2 bg-sidebar-foreground/20" />
                      <p className="text-[9px] text-sidebar-foreground/55">Corr. Dott. R. Pozzi</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-1 border-t border-sidebar-border/30">
                    <Building2 className="h-3 w-3 text-sidebar-foreground/40 shrink-0" />
                    <p className="text-[9px] text-sidebar-foreground/45 leading-tight">
                      Univ. degli Studi di Milano-Bicocca
                    </p>
                  </div>
                </div>
              </div>
            )}

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

      {/* History Modal */}
      <HistoryModal
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onLoadChat={onLoadChat}
      />

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
        "w-full justify-start gap-3 h-10 mb-1 transition-all duration-200",
        // Default State
        "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
        // Active State
        item.isActive && !isPrimary && "bg-sidebar-accent text-sidebar-foreground font-medium",
        // Primary Variant
        isPrimary && "bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary/90 hover:text-sidebar-primary-foreground shadow-sm",
        // Collapsed Logic
        isCollapsed && "justify-center px-0 w-10 h-10 mx-auto",
        // Disabled State
        disabled && "opacity-40 pointer-events-none"
      )}
      onClick={item.onClick}
    >
      <item.icon className={cn("h-5 w-5 shrink-0", isPrimary ? "text-sidebar-primary-foreground" : "text-current")} />
      {!isCollapsed && (
        <span className={cn("truncate", isPrimary && "font-medium")}>{item.label}</span>
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
      <DialogContent className="max-w-md">
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


// History Modal
function HistoryModal({ open, onClose, onLoadChat }: { open: boolean; onClose: () => void; onLoadChat?: (chat: any) => void }) {
  const [history, setHistory] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);

  const fetchHistory = async () => {
    setIsLoading(true);
    setError("");
    try {
      const res = await fetch(`${config.api.baseUrl}/history`);
      if (!res.ok) throw new Error("Failed to load history");
      const data = await res.json();
      setHistory(data.history || []);
    } catch (err) {
      console.error(err);
      setError("Errore nel caricamento della cronologia");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectChat = async (id: string) => {
    setIsLoading(true);
    try {
        const res = await fetch(`${config.api.baseUrl}/history/${id}`);
        if (!res.ok) throw new Error("Failed to load chat details");
        const data = await res.json();
        if (onLoadChat) {
            onLoadChat(data);
            onClose();
        } else {
            sessionStorage.setItem("pendingChat", JSON.stringify(data));
            window.location.href = "/";
        }
    } catch (err) {
        console.error(err);
        setError("Impossibile caricare la chat");
    } finally {
        setIsLoading(false);
    }
  };

  const handleRequestDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    e.nativeEvent.stopImmediatePropagation();
    setDeleteConfirmationId(id);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.nativeEvent.stopImmediatePropagation();
    setDeleteConfirmationId(null);
  };

  const handleConfirmDelete = async (e: React.MouseEvent, id: string) => {
      e.preventDefault();
      e.stopPropagation();
      e.nativeEvent.stopImmediatePropagation();

      try {
          const res = await fetch(`${config.api.baseUrl}/history/${id}`, { method: 'DELETE' });
          if(res.ok) {
              setHistory(prev => prev.filter(h => h.id !== id));
          }
      } catch(err) {
          console.error(err);
      } finally {
        setDeleteConfirmationId(null);
      }
  }

  useEffect(() => {
    if (open) {
        fetchHistory();
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] sm:max-w-xl bg-background border-none shadow-2xl p-0 overflow-hidden rounded-xl sm:rounded-2xl h-[85vh] sm:h-[80vh] flex flex-col">
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b border-border/40 shrink-0 bg-card/50 backdrop-blur-sm">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <History className="h-5 w-5 text-primary" />
            <span>Cronologia Chat</span>
          </DialogTitle>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <MessageCircle className="h-3 w-3" />
              {history.length} conversazion{history.length === 1 ? "e" : "i"}
            </span>
            <span className="text-muted-foreground/50">
              Le tue conversazioni precedenti
            </span>
          </div>
        </DialogHeader>

        {/* Content */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {isLoading && history.length === 0 ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
              <span className="text-sm text-muted-foreground">Caricamento cronologia...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3 px-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                <AlertCircle className="h-6 w-6 text-destructive" />
              </div>
              <p className="text-sm text-muted-foreground text-center">{error}</p>
            </div>
          ) : history.length === 0 ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-3 px-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <Inbox className="h-6 w-6 text-muted-foreground" />
              </div>
              <div className="text-center space-y-1">
                <p className="text-sm font-medium text-foreground">Nessuna conversazione</p>
                <p className="text-xs text-muted-foreground">Le tue chat appariranno qui</p>
              </div>
            </div>
          ) : (
            <ScrollArea className="flex-1 h-0 [&_[data-radix-scroll-area-viewport]>div]:!block">
              <div className="px-6 py-4 space-y-2">
                {history.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleSelectChat(item.id)}
                    className="group flex items-start gap-3 p-3 rounded-lg border border-border/50 bg-card/50 hover:bg-primary/5 hover:border-primary/20 cursor-pointer transition-colors"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 mt-0.5">
                      <MessageCircle className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <span className="font-medium text-sm line-clamp-2 text-foreground">
                        {item.query}
                      </span>
                      {item.preview && (
                        <p className="text-xs text-muted-foreground line-clamp-1">
                          {item.preview}
                        </p>
                      )}
                      <div className="flex items-center gap-1.5 pt-0.5">
                        <Clock className="h-3 w-3 text-muted-foreground/60" />
                        <span className="text-[11px] text-muted-foreground/70">
                          {new Date(item.timestamp).toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "numeric" })} · {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 pt-1">
                      {deleteConfirmationId === item.id ? (
                        <div className="flex gap-1">
                          <Button
                            variant="secondary"
                            size="icon"
                            className="h-7 w-7 bg-muted hover:bg-muted/80"
                            onClick={handleCancelDelete}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="destructive"
                            size="icon"
                            className="h-7 w-7"
                            onClick={(e) => handleConfirmDelete(e, item.id)}
                          >
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          onClick={(e) => handleRequestDelete(e, item.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
