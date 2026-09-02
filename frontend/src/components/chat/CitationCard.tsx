"use client";

import { useState, useRef, useEffect } from "react";
import { cn, toTitleCase } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Calendar, MapPin, ExternalLink, Globe, Languages, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useTranslations } from "next-intl";
import { getGroupColor, PARTY_PALETTE } from "@/config";
import type { Citation } from "@/types";

function getCameraUrl(id: string | undefined): string | null {
  if (!id) return null;
  // Match legXX_sedY_... where Y is the seduta number
  // Example: leg19_sed2_tit00040
  // Example: leg19_sed3_tit00080.int00060
  const match = id.match(/leg\d+_sed(\d+)_(.+)/);
  if (!match) return null;

  const [_, sedutaStr, rest] = match;
  const sedutaId = sedutaStr.padStart(4, '0');

  return `https://www.camera.it/leg19/410?idSeduta=${sedutaId}&tipo=stenografico#sed${sedutaId}.stenografico.${rest}`;
}

// Glifo-ancora del brand: il quadrato pieno segna il link alla fonte ufficiale
function SourceGlyph({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block h-2 w-2 shrink-0 bg-current", className)}
    />
  );
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return isMobile;
}

interface CitationCardProps {
  citation: Citation;
  index: number;
  className?: string;
  isHighlighted?: boolean;
  /** true solo per l'evidenziazione da click: l'hover non deve far scrollare */
  scrollOnHighlight?: boolean;
}

export function CitationCard({ citation, index, className, isHighlighted, scrollOnHighlight }: CitationCardProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);
  const t = useTranslations("CitationCard");

  const isGoverno = citation.group?.toLowerCase() === "governo" || !!citation.institutional_role;
  // "misto": il Gruppo Misto non è ascrivibile a uno schieramento — etichetta neutra
  const coalitionLabel = isGoverno
    ? t("governo")
    : citation.coalition === "misto" ? "Gruppo Misto" : citation.coalition;
  const partyColor = isGoverno ? PARTY_PALETTE.GOVERNO.color : getGroupColor(citation.group || "Misto");

  const displayText = citation.translated_text ?? citation.text ?? citation.quote_text ?? "";
  const originalText = citation.is_translated ? (citation.text ?? citation.quote_text ?? "") : null;
  const interventionUrl = getCameraUrl(citation.intervention_id);

  // Auto-scroll solo per il click sull'inline citation, non per l'hover
  useEffect(() => {
    if (scrollOnHighlight && cardRef.current) {
        cardRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [scrollOnHighlight]);

  return (
    <>
      {/* Blocco citazione: angoli vivi + filetto sinistro — la prova, non una card */}
      <div
        ref={cardRef}
        role="button"
        tabIndex={0}
        aria-label={`${toTitleCase(citation.deputy_first_name || "")} ${toTitleCase(citation.deputy_last_name || "")}, ${citation.date}`}
        className={cn(
          "cursor-pointer w-full max-w-full bg-card border-y border-r border-transparent border-l-2 border-l-foreground/70 transition-colors duration-200",
          "hover:bg-accent/40 hover:border-l-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
          isHighlighted && "border-l-primary bg-primary/5 ring-1 ring-primary/25",
          className
        )}
        onClick={() => setIsDrawerOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setIsDrawerOpen(true);
          }
        }}
      >
        <div className="p-3.5">
          {/* Chi parla */}
          <div className="flex items-center gap-2 min-w-0">
            <span
              aria-hidden="true"
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: partyColor }}
            />
            {citation.camera_profile_url ? (
                <a
                    href={citation.camera_profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-semibold text-foreground truncate min-w-0 hover:underline hover:text-primary transition-colors"
                    onClick={(e) => e.stopPropagation()}
                >
                    {toTitleCase(citation.deputy_first_name || "")} {toTitleCase(citation.deputy_last_name || "")}
                </a>
            ) : (
                <span className="text-sm font-semibold text-foreground truncate min-w-0">
                    {toTitleCase(citation.deputy_first_name || "")} {toTitleCase(citation.deputy_last_name || "")}
                </span>
            )}
            <Badge
              variant="outline"
              className="shrink-0 text-[10px] px-1.5 py-0 h-5 ml-auto capitalize border-border text-muted-foreground rounded-sm"
            >
              {coalitionLabel}
            </Badge>
          </div>
          {!isGoverno && (
            <span className="text-[10px] text-muted-foreground block max-w-full break-words mt-0.5 pl-4" title={citation.misto_component ? `${citation.group} – ${citation.misto_component}` : citation.group}>
              {citation.misto_component
                ? `${citation.group} – ${citation.misto_component}`
                : citation.group}
            </span>
          )}

          {/* Quando e dove — dato, quindi mono */}
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] text-muted-foreground mt-1.5 pl-4 max-w-full">
            <span className="flex items-center gap-1 shrink-0">
              <Calendar className="h-3 w-3" aria-hidden="true" />
              {citation.date}
            </span>
            {citation.debate && (
              <span className="min-w-0 truncate max-w-full" title={citation.debate}>
                {citation.debate}
              </span>
            )}
          </div>

          {/* La quote: voce editoriale */}
          {originalText ? (
            <Tooltip delayDuration={300}>
              <TooltipTrigger asChild>
                <p className="[font-family:var(--font-display)] italic text-sm text-foreground/80 line-clamp-2 mt-2 leading-relaxed break-words cursor-help pl-4">
                  &ldquo;{displayText}&rdquo;
                  <Globe className="inline h-3 w-3 ml-1 text-muted-foreground/50" aria-label={t("originalLabel")} />
                </p>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[400px] p-3">
                <p className="text-[10px] font-semibold text-muted-foreground/70 mb-1 uppercase tracking-wider">{t("originalLabel")}</p>
                <p className="text-xs leading-relaxed italic">{originalText}</p>
              </TooltipContent>
            </Tooltip>
          ) : (
            <p className="[font-family:var(--font-display)] italic text-sm text-foreground/80 line-clamp-2 mt-2 leading-relaxed break-words pl-4">
              &ldquo;{displayText}&rdquo;
            </p>
          )}

          {/* Ancora alla fonte */}
          {interventionUrl && (
            <a
              href={interventionUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 mt-2 ml-4 text-[11px] font-medium text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <SourceGlyph />
              {t("goToIntervention")}
            </a>
          )}
        </div>
      </div>

      {/* Drawer con la catena completa fino alla fonte */}
      <CitationDrawer
        citation={citation}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />
    </>
  );
}

interface CitationDrawerProps {
  citation: Citation;
  isOpen: boolean;
  onClose: () => void;
}

// Desktop: drawer laterale (la risposta resta visibile). Mobile: bottom sheet.
function CitationDrawer({ citation, isOpen, onClose }: CitationDrawerProps) {
  const t = useTranslations("CitationCard");
  const isMobile = useIsMobile();
  const isGoverno = citation.group?.toLowerCase() === "governo" || !!citation.institutional_role;
  const coalitionLabel = isGoverno
    ? t("governo")
    : citation.coalition === "misto" ? "Gruppo Misto" : citation.coalition;
  const partyColor = isGoverno ? PARTY_PALETTE.GOVERNO.color : getGroupColor(citation.group || "Misto");
  // On-demand translation state for the full speech text
  const [translatedFull, setTranslatedFull] = useState<string | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslated, setShowTranslated] = useState(false);

  // Use pre-translated full_text if available, otherwise use on-demand translation
  const preTranslatedFull = citation.translated_full_text && citation.translated_full_text.length > 0
    ? citation.translated_full_text : null;
  const hasTranslation = !!(preTranslatedFull || translatedFull);
  const displayFullText = (showTranslated && (preTranslatedFull || translatedFull))
    ? (preTranslatedFull || translatedFull)!
    : (citation.full_text ?? citation.text ?? "");
  const originalFullText = (showTranslated && hasTranslation)
    ? (citation.full_text ?? citation.text ?? "") : null;

  const handleTranslate = async () => {
    if (preTranslatedFull || translatedFull) {
      setShowTranslated(true);
      return;
    }
    const textToTranslate = citation.full_text ?? citation.text ?? "";
    if (!textToTranslate) return;

    setIsTranslating(true);
    try {
      const resp = await fetch("/api/config/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToTranslate }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setTranslatedFull(data.translated || textToTranslate);
        setShowTranslated(true);
      }
    } catch {
      // Silently fail — show original
    } finally {
      setIsTranslating(false);
    }
  };

  // When the UI is in English (citation.is_translated), show the English
  // full text by default: auto-translate on first open.
  useEffect(() => {
    if (isOpen && citation.is_translated && !hasTranslation && !isTranslating) {
      handleTranslate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);
  const displayText = displayFullText;

  const contextUrl = getCameraUrl(citation.debate_id);
  const interventionUrl = getCameraUrl(citation.intervention_id);

  // Highlighting logic: only highlight if we have a specific quote_text that differs from full_text
  // Don't try to highlight the entire chunk - it doesn't make sense
  const quoteText = citation.quote_text || "";
  const hasSpecificQuote = quoteText && citation.full_text &&
    quoteText.length < citation.full_text.length * 0.8; // Quote should be notably shorter than full text

  // Use the active display text for highlighting (translated or original)
  const textForHighlight = displayFullText;
  let parts: string[] = [textForHighlight];
  const highlightText = quoteText;

  // Only highlight in original Italian text (quotes won't match in translated text)
  if (hasSpecificQuote && !showTranslated && citation.full_text) {
    if (citation.full_text.includes(quoteText)) {
      parts = citation.full_text.split(quoteText);
    } else {
      const normalize = (s: string) => s.replace(/\s+/g, ' ').trim();
      const normalizedQuote = normalize(quoteText);
      const normalizedFull = normalize(citation.full_text);

      if (normalizedFull.includes(normalizedQuote)) {
        try {
          const escaped = quoteText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          const pattern = escaped.replace(/\s+/g, '\\s+');
          const regex = new RegExp(pattern, 'i');
          parts = citation.full_text.split(regex);
        } catch {
          // Keep parts as [textForHighlight]
        }
      }
    }
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent
        side={isMobile ? "bottom" : "right"}
        className={cn(
          "p-0 flex flex-col gap-0 bg-background",
          isMobile ? "h-[88dvh] rounded-t-lg" : "w-full sm:max-w-xl"
        )}
      >
        {/* Speaker bar */}
        <SheetHeader className="px-5 py-4 border-b border-border shrink-0 space-y-0 text-left">
          <SheetTitle className="sr-only">{t("intervention")}</SheetTitle>
          <SheetDescription className="sr-only">
            {toTitleCase(citation.deputy_first_name || "")} {toTitleCase(citation.deputy_last_name || "")} · {citation.date}
          </SheetDescription>
          <div className="flex items-center gap-3 min-w-0 pr-8">
            {citation.photo ? (
                <img
                    src={citation.photo}
                    alt=""
                    className="h-11 w-11 shrink-0 rounded-full object-cover border"
                    style={{ borderColor: `${partyColor}40` }}
                    onError={(e) => {
                        const target = e.currentTarget;
                        target.style.display = "none";
                        const next = target.nextElementSibling as HTMLElement | null;
                        if (next) next.style.display = "flex";
                    }}
                />
            ) : null}
            <div
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border text-base font-bold"
                style={{ color: partyColor, borderColor: `${partyColor}40`, backgroundColor: `${partyColor}0d`, display: citation.photo ? "none" : "flex" }}
            >
                {citation.deputy_first_name?.[0]}{citation.deputy_last_name?.[0]}
            </div>
            <div className="flex flex-col min-w-0">
                {citation.camera_profile_url ? (
                    <a
                        href={citation.camera_profile_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="[font-family:var(--font-display)] font-semibold tracking-tight text-foreground text-base leading-tight truncate hover:underline hover:text-primary transition-colors"
                    >
                        {toTitleCase(citation.deputy_first_name || "")} {toTitleCase(citation.deputy_last_name || "")}
                    </a>
                ) : (
                    <div className="[font-family:var(--font-display)] font-semibold tracking-tight text-foreground text-base leading-tight truncate">
                        {toTitleCase(citation.deputy_first_name || "")} {toTitleCase(citation.deputy_last_name || "")}
                    </div>
                )}
                <div className="flex items-center gap-2 mt-1 min-w-0">
                     <span
                       aria-hidden="true"
                       className="h-2 w-2 rounded-full shrink-0"
                       style={{ backgroundColor: partyColor }}
                     />
                     <span className="text-xs text-muted-foreground truncate capitalize" title={citation.misto_component ? `${citation.group} – ${citation.misto_component}` : citation.group}>
                        {isGoverno
                          ? coalitionLabel
                          : citation.misto_component
                            ? `${citation.group} – ${citation.misto_component}`
                            : citation.group}
                     </span>
                     <span className="font-mono text-[11px] text-muted-foreground shrink-0 ml-auto flex items-center gap-1">
                        <Calendar className="w-3 h-3" aria-hidden="true" />
                        {citation.date}
                     </span>
                </div>
            </div>
          </div>
        </SheetHeader>

        {/* Content */}
        <ScrollArea className="flex-1 min-h-0">
            <div className="p-5 md:p-6 space-y-6">
                {/* Contesto: la seduta */}
                {citation.debate && (
                    <div className="border-l-2 border-l-foreground/70 pl-3 text-sm leading-relaxed text-muted-foreground">
                        <div className="flex items-center gap-1.5 mb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                            <MapPin className="w-3 h-3" aria-hidden="true" />
                            {t("parliamentaryContext")}
                        </div>
                        {contextUrl ? (
                            <a
                                href={contextUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="hover:text-primary hover:underline transition-colors inline-flex items-center gap-1 group/link"
                            >
                                {citation.debate}
                                <ExternalLink className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity shrink-0" aria-hidden="true" />
                            </a>
                        ) : (
                            citation.debate
                        )}
                    </div>
                )}

                {/* Translation-in-progress banner */}
                {isTranslating && (
                    <div className="flex items-center gap-2 border border-primary/20 bg-primary/5 px-3 py-2 text-xs font-medium text-primary" role="status">
                        <Loader2 className="h-3.5 w-3.5 motion-safe:animate-spin shrink-0" aria-hidden="true" />
                        {t("translating")}
                    </div>
                )}

                {/* Il testo integrale, con la quote evidenziata */}
                <div className={cn(
                    "[font-family:var(--font-display)] text-[15px] leading-loose text-foreground/90 max-w-[68ch]",
                    isTranslating && "opacity-50 transition-opacity"
                )}>
                    {parts.length > 1 ? (
                        <>
                            {parts.map((part, i) => (
                                <span key={i}>
                                    {part}
                                    {i < parts.length - 1 && (
                                        <mark className="bg-primary/10 text-foreground px-1 -mx-1 border-b-2 border-primary/60 font-medium">
                                            {highlightText}
                                        </mark>
                                    )}
                                </span>
                            ))}
                        </>
                    ) : (
                        displayText
                    )}
                    {citation.is_translated && (
                        <Globe className="inline h-4 w-4 ml-2 text-muted-foreground/40 align-middle" aria-label={t("originalLabel")} />
                    )}
                </div>

                {/* Translate button + original text section */}
                {citation.is_translated && !isTranslating && (
                    <div className="pt-4 border-t border-border">
                        <div className="flex items-center gap-2 mb-3">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    if (showTranslated) {
                                        setShowTranslated(false);
                                    } else {
                                        handleTranslate();
                                    }
                                }}
                                disabled={isTranslating}
                                className="text-xs h-7 gap-1.5"
                            >
                                {showTranslated ? (
                                    <><Globe className="h-3 w-3" aria-hidden="true" /> {t("showOriginal")}</>
                                ) : (
                                    <><Languages className="h-3 w-3" aria-hidden="true" /> {t("translate")}</>
                                )}
                            </Button>
                        </div>
                        {originalFullText && (
                            <>
                                <p className="font-mono text-[10px] font-semibold text-muted-foreground/70 mb-2 uppercase tracking-wider flex items-center gap-1.5">
                                    <Globe className="h-3 w-3" aria-hidden="true" />
                                    {t("originalLabel")}
                                </p>
                                <p className="[font-family:var(--font-display)] text-sm leading-relaxed italic text-muted-foreground/80">{originalFullText}</p>
                            </>
                        )}
                    </div>
                )}
            </div>
        </ScrollArea>

        {/* L'ancora: sempre visibile, chiude la catena sulla fonte ufficiale */}
        {interventionUrl && (
            <div className="border-t border-border p-4 shrink-0 bg-background">
                <Button asChild className="w-full gap-2">
                    <a href={interventionUrl} target="_blank" rel="noopener noreferrer">
                        <span aria-hidden="true" className="inline-block h-2 w-2 bg-current" />
                        {t("goToCamera")}
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                </Button>
            </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
