"use client";

import { useState, useEffect, useRef } from "react";
import { Search, User, X, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { config } from "@/config";

export interface Deputy {
  id: string;
  nome: string;
  cognome: string;
  gruppo?: string;
  imgUrl?: string;
}

interface DeputySelectorProps {
  selectedDeputy: Deputy | null;
  onSelect: (deputy: Deputy | null) => void;
}

export function DeputySelector({ selectedDeputy, onSelect }: DeputySelectorProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Deputy[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Debounce logic
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (query.length < 2) {
        setSuggestions([]);
        return;
      }
      
      setLoading(true);
      try {
        const res = await fetch(`${config.api.baseUrl}/search/deputies?q=${encodeURIComponent(query)}`);
        if (res.ok) {
            const data = await res.json();
            setSuggestions(data);
            setIsOpen(true);
        }
      } catch (err) {
        console.error("Error fetching deputies:", err);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (selectedDeputy) {
    return (
        <div className="flex items-center gap-3 p-3 border rounded-lg bg-accent/20">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0 overflow-hidden">
                {selectedDeputy.imgUrl ? (
                    <img src={selectedDeputy.imgUrl} alt="Foto" className="h-full w-full object-cover" />
                ) : (
                    <User className="h-5 w-5 text-primary" />
                )}
            </div>
            <div className="flex-1 min-w-0 user-select-none">
                <p className="font-medium text-sm truncate">
                    {selectedDeputy.nome} {selectedDeputy.cognome}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                    {selectedDeputy.gruppo || "Deputato"}
                </p>
            </div>
            <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => {
                    onSelect(null);
                    setQuery("");
                }}
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
            >
                <X className="h-4 w-4" />
            </Button>
        </div>
    );
  }

  return (
    <div className="relative w-full" ref={wrapperRef}>
        <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
                placeholder="Cerca deputato (es. Giuseppe Conte)..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
                onFocus={() => {
                    if(suggestions.length > 0) setIsOpen(true);
                }}
            />
            {loading && (
                <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-muted-foreground" />
            )}
        </div>

        {isOpen && suggestions.length > 0 && (
            <Card className="absolute top-full mt-1 w-full z-50 max-h-60 overflow-y-auto shadow-lg border-border bg-popover">
                <ul className="py-1">
                    {suggestions.map((deputy) => (
                        <li 
                            key={deputy.id}
                            className="px-3 py-2 hover:bg-accent hover:text-accent-foreground cursor-pointer flex items-center gap-3 transition-colors"
                            onClick={() => {
                                onSelect(deputy);
                                setIsOpen(false);
                            }}
                        >
                            <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                                <User className="h-4 w-4 text-muted-foreground" />
                            </div>
                            <div className="min-w-0">
                                <p className="text-sm font-medium">
                                    {deputy.nome} {deputy.cognome}
                                </p>
                                <p className="text-xs text-muted-foreground truncate">
                                    {deputy.gruppo}
                                </p>
                            </div>
                        </li>
                    ))}
                </ul>
            </Card>
        )}
    </div>
  );
}
