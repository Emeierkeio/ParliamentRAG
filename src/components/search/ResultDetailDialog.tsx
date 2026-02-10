"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { config } from "@/config";
import {
  MessageSquareQuote,
  Calendar,
  FileText,
  ExternalLink,
  User,
  Building2,
  Tag,
  Loader2,
  Sparkles,
} from "lucide-react";
import { SearchResultItem } from "./ResultsList";
import {
  getActTypeLabel,
  getActTypeColor,
  getGroupColor,
  getGroupShortLabel,
} from "./ResultsList";

interface SpeechDetail {
  type: "speech";
  id: string;
  speech_id: string;
  full_text: string;
  chunk_text: string;
  date: string;
  session_number: number | null;
  debate_title: string;
  first_name: string;
  last_name: string;
  group: string;
}

interface ActDetail {
  type: "act";
  id: string;
  act_type: string;
  act_title: string;
  description: string;
  date: string;
  act_number: string;
  destinatario: string;
  eurovoc: string;
  first_name: string;
  last_name: string;
  group: string;
}

type DetailData = SpeechDetail | ActDetail;

interface ResultDetailDialogProps {
  item: SearchResultItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatDate(dateString: string) {
  try {
    if (!dateString) return "";
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString("it-IT", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

export function ResultDetailDialog({
  item,
  open,
  onOpenChange,
}: ResultDetailDialogProps) {
  const [detail, setDetail] = useState<DetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !item) {
      setDetail(null);
      setError(null);
      return;
    }

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const endpoint =
          item.type === "speech"
            ? `${config.api.baseUrl}/search/speech/${encodeURIComponent(item.id)}`
            : `${config.api.baseUrl}/search/act/${encodeURIComponent(item.id)}`;

        const res = await fetch(endpoint);
        if (!res.ok) throw new Error("Impossibile caricare i dettagli");
        const data = await res.json();
        setDetail(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Errore sconosciuto");
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [open, item]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12 space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Caricamento...</p>
          </div>
        )}

        {error && (
          <div className="text-center py-8 text-destructive">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && detail && detail.type === "speech" && (
          <SpeechDetailContent detail={detail as SpeechDetail} item={item!} />
        )}

        {!loading && !error && detail && detail.type === "act" && (
          <ActDetailContent detail={detail as ActDetail} item={item!} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function SpeechDetailContent({
  detail,
  item,
}: {
  detail: SpeechDetail;
  item: SearchResultItem;
}) {
  const groupColor = getGroupColor(detail.group);

  return (
    <>
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <MessageSquareQuote className="h-5 w-5 text-primary shrink-0" />
          <DialogTitle className="text-lg">
            Seduta n. {detail.session_number} del {formatDate(detail.date)}
          </DialogTitle>
        </div>
        {detail.debate_title && (
          <p className="text-sm text-muted-foreground pl-7">
            {detail.debate_title}
          </p>
        )}
      </DialogHeader>

      <div className="space-y-4 mt-2">
        {/* Speaker info */}
        <div className="flex items-center gap-2">
          <User className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="font-semibold text-foreground">
            {detail.first_name} {detail.last_name}
          </span>
          <Badge
            variant="secondary"
            className="text-xs px-2 py-0"
            style={{
              backgroundColor: `${groupColor}20`,
              color: groupColor,
              borderColor: `${groupColor}40`,
            }}
          >
            {getGroupShortLabel(detail.group)}
          </Badge>
          {item.match_type === "semantic" && item.score != null && (
            <Badge
              variant="secondary"
              className="text-xs gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300 ml-auto"
            >
              <Sparkles className="h-3 w-3" />
              {(item.score * 100).toFixed(0)}%
            </Badge>
          )}
        </div>

        {/* Full text */}
        <div className="pl-4 border-l-2 border-primary/20 text-sm leading-relaxed text-foreground whitespace-pre-line max-h-[50vh] overflow-y-auto">
          {detail.full_text}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-3 w-3" />
            {formatDate(detail.date)}
          </div>
          {detail.session_number && (
            <a
              href={`https://www.camera.it/leg19/410?idSeduta=${detail.session_number}&tipo=seduta`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              Vedi fonte ufficiale <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </>
  );
}

function ActDetailContent({
  detail,
  item,
}: {
  detail: ActDetail;
  item: SearchResultItem;
}) {
  const groupColor = getGroupColor(detail.group);
  const typeLabel = getActTypeLabel(detail.act_type);
  const typeColor = getActTypeColor(detail.act_type);

  const topics = detail.eurovoc
    ? detail.eurovoc
        .split(";")
        .map((t) => t.trim())
        .filter(Boolean)
    : [];

  return (
    <>
      <DialogHeader>
        <div className="flex items-center gap-2 mb-1">
          <FileText className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <Badge className={`text-xs font-semibold ${typeColor}`}>
            {typeLabel}
          </Badge>
          {detail.act_number && (
            <span className="text-sm text-muted-foreground font-mono">
              n. {detail.act_number}
            </span>
          )}
          {item.match_type === "semantic" && item.score != null && (
            <Badge
              variant="secondary"
              className="text-xs gap-1 bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300 ml-auto"
            >
              <Sparkles className="h-3 w-3" />
              {(item.score * 100).toFixed(0)}%
            </Badge>
          )}
        </div>
        {detail.act_title && (
          <DialogTitle className="text-base pl-7">
            {detail.act_title}
          </DialogTitle>
        )}
      </DialogHeader>

      <div className="space-y-4 mt-2">
        {/* Signatory */}
        <div className="flex items-center gap-2">
          <User className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="text-xs text-muted-foreground">
            Primo firmatario:
          </span>
          <span className="font-semibold text-sm text-foreground">
            {detail.first_name} {detail.last_name}
          </span>
          <Badge
            variant="secondary"
            className="text-xs px-2 py-0"
            style={{
              backgroundColor: `${groupColor}20`,
              color: groupColor,
              borderColor: `${groupColor}40`,
            }}
          >
            {getGroupShortLabel(detail.group)}
          </Badge>
        </div>

        {/* Destinatario */}
        {detail.destinatario && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Building2 className="h-4 w-4 shrink-0" />
            <span>
              Destinatario:{" "}
              <span className="font-medium text-foreground">
                {detail.destinatario}
              </span>
            </span>
          </div>
        )}

        {/* Full description */}
        {detail.description && (
          <div className="pl-4 border-l-2 border-emerald-500/20 text-sm leading-relaxed text-foreground whitespace-pre-line max-h-[50vh] overflow-y-auto">
            {detail.description}
          </div>
        )}

        {/* EuroVoc topics */}
        {topics.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <Tag className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            {topics.map((topic, i) => (
              <Badge
                key={i}
                variant="secondary"
                className="text-xs px-2 py-0.5 font-normal"
              >
                {topic}
              </Badge>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-3 w-3" />
            {formatDate(detail.date)}
          </div>
        </div>
      </div>
    </>
  );
}
