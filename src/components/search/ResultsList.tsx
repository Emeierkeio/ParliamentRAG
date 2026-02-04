"use client";

import { MessageSquareQuote, Calendar, FileText, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export interface SearchResultItem {
  chunk_id: string;
  testo: string;
  intervento_id: string;
  data: string;
  seduta_numero: number;
  dibattito_titolo: string;
  nome: string;
  cognome: string;
  gruppo: string;
}

interface ResultsListProps {
  results: SearchResultItem[];
  query: string;
}

export function ResultsList({ results, query }: ResultsListProps) {
  if (results.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
        Nessun risultato trovato. Riprova con altri criteri.
      </div>
    );
  }

  const formatDate = (dateString: string) => {
      try {
          if (!dateString) return "";
          const date = new Date(dateString);
          if (isNaN(date.getTime())) return dateString; // Fallback to raw string
          return date.toLocaleDateString("it-IT", {
              day: "numeric",
              month: "long",
              year: "numeric"
          });
      } catch (e) {
          return dateString;
      }
  };

  // Funzione per evidenziare il testo
  const highlightText = (text: string, highlight: string) => {
    if (!highlight.trim()) return text;
    const parts = text.split(new RegExp(`(${highlight})`, 'gi'));
    return (
      <span>
        {parts.map((part, i) => 
          part.toLowerCase() === highlight.toLowerCase() ? (
            <span key={i} className="bg-yellow-200 dark:bg-yellow-900/50 text-foreground font-medium px-0.5 rounded">
              {part}
            </span>
          ) : (
            part
          )
        )}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      {results.map((item) => (
        <Card key={item.chunk_id} className="overflow-hidden hover:shadow-md transition-shadow">
          <CardHeader className="bg-muted/30 pb-3 pt-4 px-4">
            <div className="flex justify-between items-start gap-4">
                <div className="space-y-1">
                    <CardTitle className="text-base font-medium flex items-center gap-2">
                        <MessageSquareQuote className="h-4 w-4 text-primary" />
                        Seduta n. {item.seduta_numero} del {formatDate(item.data)}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground line-clamp-1">
                        {item.dibattito_titolo}
                    </p>
                </div>
                <Badge variant="outline" className="whitespace-nowrap shrink-0">
                    <FileText className="h-3 w-3 mr-1" />
                    Atto
                </Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-4 px-4 pb-4">
            <div className="relative">
                <div className="pl-4 border-l-2 border-primary/20 text-sm leading-relaxed text-muted-foreground">
                    {highlightText(item.testo, query)}
                </div>
            </div>
            
            <div className="mt-4 flex items-center justify-end gap-2">
                 <a 
                    href={`https://www.camera.it/leg19/410?idSeduta=${item.seduta_numero}&tipo=seduta`}
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                    Vedi fonte ufficiale <ExternalLink className="h-3 w-3" />
                </a>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
