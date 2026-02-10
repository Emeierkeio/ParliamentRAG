"use client";

import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

const GROUPS: { value: string; label: string }[] = [
    { value: "FRATELLI D'ITALIA", label: "Fratelli d'Italia" },
    { value: "LEGA - SALVINI PREMIER", label: "Lega - Salvini Premier" },
    { value: "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE", label: "Forza Italia - Berlusconi Presidente - PPE" },
    { value: "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE", label: "Noi Moderati - MAIE - Centro Popolare" },
    { value: "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA", label: "Partito Democratico - Italia Democratica e Progressista" },
    { value: "MOVIMENTO 5 STELLE", label: "Movimento 5 Stelle" },
    { value: "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE", label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    { value: "ITALIA VIVA-IL CENTRO-RENEW EUROPE", label: "Italia Viva - Il Centro - Renew Europe" },
    { value: "ALLEANZA VERDI E SINISTRA", label: "Alleanza Verdi e Sinistra" },
    { value: "MISTO", label: "Misto" },
];

interface GroupSelectorProps {
  selectedGroup: string | null;
  onSelect: (group: string | null) => void;
}

export function GroupSelector({ selectedGroup, onSelect }: GroupSelectorProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal text-left h-10"
        >
          {selectedGroup ? (
              <span className="truncate">{GROUPS.find(g => g.value === selectedGroup)?.label ?? selectedGroup}</span>
          ) : (
             <span className="text-muted-foreground">Seleziona un gruppo...</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full p-0" align="start">
        <Command>
          <CommandInput placeholder="Cerca gruppo..." />
          <CommandList>
            <CommandEmpty>Nessun gruppo trovato.</CommandEmpty>
            <CommandGroup>
              <CommandItem value="all" onSelect={() => { onSelect(null); setOpen(false); }}>
                <Check className={cn("mr-2 h-4 w-4", !selectedGroup ? "opacity-100" : "opacity-0")} />
                Tutti i gruppi
              </CommandItem>
              {GROUPS.map((group) => (
                <CommandItem
                  key={group.value}
                  value={group.value}
                  onSelect={(currentValue) => {
                    onSelect(currentValue === selectedGroup ? null : currentValue);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      selectedGroup === group.value ? "opacity-100" : "opacity-0"
                    )}
                  />
                  {group.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
