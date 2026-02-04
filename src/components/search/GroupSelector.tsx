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

const GROUPS = [
    "FRATELLI D'ITALIA",
    "LEGA - SALVINI PREMIER",
    "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE", 
    "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE",
    "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA",
    "MOVIMENTO 5 STELLE",
    "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE",
    "ITALIA VIVA-IL CENTRO-RENEW EUROPE",
    "ALLEANZA VERDI E SINISTRA",
    "MISTO"
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
              <span className="truncate">{selectedGroup}</span>
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
                  key={group}
                  value={group}
                  onSelect={(currentValue) => {
                    onSelect(currentValue === selectedGroup ? null : currentValue);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      selectedGroup === group ? "opacity-100" : "opacity-0"
                    )}
                  />
                  {group}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
