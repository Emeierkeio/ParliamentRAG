"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  History,
  Trash2,
  Check,
  X,
  Loader2,
  MessageCircle,
  Clock,
  Inbox,
  AlertCircle,
} from "lucide-react";
import { config } from "@/config";

interface HistoryModalProps {
  open: boolean;
  onClose: () => void;
  onLoadChat?: (chat: any) => void;
}

export function HistoryModal({ open, onClose, onLoadChat }: HistoryModalProps) {
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
      const res = await fetch(`${config.api.baseUrl}/history/${id}`, { method: "DELETE" });
      if (res.ok) {
        setHistory((prev) => prev.filter((h) => h.id !== id));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDeleteConfirmationId(null);
    }
  };

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
            <span className="text-muted-foreground/50">Le tue conversazioni precedenti</span>
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
                        <p className="text-xs text-muted-foreground line-clamp-1">{item.preview}</p>
                      )}
                      <div className="flex items-center gap-1.5 pt-0.5">
                        <Clock className="h-3 w-3 text-muted-foreground/60" />
                        <span className="text-[11px] text-muted-foreground/70">
                          {new Date(item.timestamp).toLocaleDateString("it-IT", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                          })}{" "}
                          ·{" "}
                          {new Date(item.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 pt-1">
                      {deleteConfirmationId === item.id ? (
                        <div className="flex gap-1">
                          <Button
                            variant="secondary"
                            size="icon"
                            className="h-9 w-9 min-tap-none bg-muted hover:bg-muted/80"
                            onClick={handleCancelDelete}
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="destructive"
                            size="icon"
                            className="h-9 w-9 min-tap-none"
                            onClick={(e) => handleConfirmDelete(e, item.id)}
                          >
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 min-tap-none opacity-0 group-hover:opacity-100 [@media(pointer:coarse)]:opacity-100 transition-opacity text-muted-foreground hover:text-destructive hover:bg-destructive/10"
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
