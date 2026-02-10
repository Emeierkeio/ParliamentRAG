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
import {
  MessageSquare,
  PanelLeftClose,
  PanelLeft,
  History,
  Info,
  Landmark,
  Github,
  ExternalLink,
  Database,
  Trash2,
  Check,
  Search,
  X,
  ClipboardCheck,
} from "lucide-react";
import { config } from "@/config";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  onNewChat?: () => void;
  onLoadChat?: (chat: any) => void;
  isQueryRunning?: boolean;
}

export function Sidebar({ isCollapsed, onToggle, onNewChat, onLoadChat, isQueryRunning = false }: SidebarProps) {
  const [infoOpen, setInfoOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  return (
    <>
      <aside
        className={cn(
          "flex h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 ease-out",
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
            <div className={cn("flex items-center gap-3 transition-opacity duration-300", isCollapsed && "w-10 justify-center")}>
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                <Landmark className="h-5 w-5" />
              </div>
              {!isCollapsed && (
                <div className="flex flex-col fade-in">
                  <span className="text-sm font-bold tracking-tight text-foreground">
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
                  className="h-8 w-8 text-muted-foreground hover:bg-transparent hover:text-foreground ml-auto"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </Button>
            )}
          </div>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 py-6 px-3">
          <nav className="flex flex-col gap-2">
            <div className="mb-6">
                <NavButton
                item={{ icon: MessageSquare, label: "Nuova Analisi", isActive: true, onClick: onNewChat }}
                isCollapsed={isCollapsed}
                variant="primary"
                />
            </div>
            
            <NavButton
              item={{ icon: History, label: "Cronologia", onClick: () => setHistoryOpen(true) }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />

            <NavButton
              item={{ icon: Search, label: "Ricerca", href: "/search", onClick: () => window.location.href = "/search" }}
              isCollapsed={isCollapsed}
              disabled={isQueryRunning}
            />

            <NavButton
              item={{ icon: Database, label: "Graph Explorer", href: "/explorer", onClick: () => window.location.href = "/explorer" }}
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
              item={{ icon: Info, label: "Informazioni", onClick: () => setInfoOpen(true) }}
              isCollapsed={isCollapsed}
            />

            <NavButton
                item={{ icon: Github, label: "Documentazione", onClick: () => window.open("https://github.com/Emeierkeio/thesis-ParliamentRAG", "_blank") }}
                isCollapsed={isCollapsed}
            />

            {/* Expand button when collapsed - at very bottom */}
            {isCollapsed && (
              <div className="mt-4 flex justify-center pt-4 border-t border-sidebar-border">
                <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={onToggle}
                        className="h-10 w-10 text-muted-foreground hover:text-foreground transition-colors"
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
        "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
        // Active State
        item.isActive && !isPrimary && "bg-sidebar-accent text-foreground font-medium",
        // Primary Variant
        isPrimary && "bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground shadow-sm",
        // Collapsed Logic
        isCollapsed && "justify-center px-0 w-10 h-10 mx-auto",
        // Disabled State
        disabled && "opacity-40 pointer-events-none"
      )}
      onClick={item.onClick}
    >
      <item.icon className={cn("h-5 w-5 shrink-0", isPrimary ? "text-primary-foreground" : "text-current")} />
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
            <Landmark className="h-5 w-5 text-primary" />
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
    if (!onLoadChat) return;
    setIsLoading(true);
    try {
        const res = await fetch(`${config.api.baseUrl}/history/${id}`);
        if (!res.ok) throw new Error("Failed to load chat details");
        const data = await res.json();
        onLoadChat(data);
        onClose();
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
  
  // Use useEffect to fetch data when modal opens
  useEffect(() => {
    if (open) {
        fetchHistory();
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-5 w-5 text-primary" />
            Cronologia Chat
          </DialogTitle>
          <DialogDescription>
            Le tue conversazioni precedenti
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col pt-4">
            {isLoading && history.length === 0 ? (
                 <div className="flex justify-center items-center h-40">
                     <span className="loading loading-spinner text-primary">Caricamento...</span>
                 </div>
            ) : error ? (
                <div className="text-red-500 text-center p-4">{error}</div>
            ) : history.length === 0 ? (
                <div className="text-center text-muted-foreground p-8">
                    Nessuna conversazione salvata.
                </div>
            ) : (
                <ScrollArea className="flex-1 pr-4">
                    <div className="space-y-3">
                        {history.map((item) => (
                            <div
                                key={item.id}
                                onClick={() => handleSelectChat(item.id)}
                                className="group flex flex-col gap-2 p-3 rounded-lg border border-border hover:bg-accent/50 cursor-pointer transition-colors"
                            >
                                <span className="font-medium text-sm line-clamp-2">{item.query}</span>
                                <p className="text-xs text-muted-foreground line-clamp-1">
                                    {item.preview}
                                </p>
                                <div className="flex justify-between items-center pt-1">
                                    <span className="text-xs text-muted-foreground">
                                        {new Date(item.timestamp).toLocaleDateString()}
                                    </span>
                                    {deleteConfirmationId === item.id ? (
                                        <div className="flex gap-1">
                                            <Button
                                                variant="secondary"
                                                size="icon"
                                                className="h-6 w-6 bg-muted hover:bg-muted/80"
                                                onClick={handleCancelDelete}
                                            >
                                                <X className="h-3 w-3" />
                                            </Button>
                                            <Button
                                                variant="destructive"
                                                size="icon"
                                                className="h-6 w-6"
                                                onClick={(e) => handleConfirmDelete(e, item.id)}
                                            >
                                                <Check className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    ) : (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-destructive/10"
                                            onClick={(e) => handleRequestDelete(e, item.id)}
                                        >
                                            <Trash2 className="h-3 w-3 text-destructive" />
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
