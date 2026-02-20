"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Plus, Trash2, Lock, Save, RefreshCw, AlertCircle, BookOpen, Pencil } from "lucide-react";
import { getAcronyms, updateAcronyms } from "@/lib/api";
import type { AcronymsData } from "@/lib/api";

export function AcronymsEditor() {
  const [data, setData] = useState<AcronymsData | null>(null);
  const [custom, setCustom] = useState<Record<string, string>>({});
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getAcronyms();
      setData(result);
      setCustom(result.custom);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore nel caricamento");
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdd = () => {
    const key = newKey.trim().toUpperCase();
    const value = newValue.trim();
    if (!key || !value) return;
    setCustom((prev) => ({ ...prev, [key]: value }));
    setNewKey("");
    setNewValue("");
  };

  const handleDelete = (key: string) => {
    setCustom((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleStartEdit = (key: string, value: string) => {
    setEditingKey(key);
    setEditingValue(value);
  };

  const handleConfirmEdit = () => {
    if (!editingKey || !editingValue.trim()) return;
    setCustom((prev) => ({ ...prev, [editingKey]: editingValue.trim() }));
    setEditingKey(null);
    setEditingValue("");
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const result = await updateAcronyms({ custom_acronyms: custom });
      setData(result);
      setCustom(result.custom);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore nel salvataggio");
    } finally {
      setIsSaving(false);
    }
  };

  const customEntries = Object.entries(custom).sort(([a], [b]) => a.localeCompare(b));
  const builtInEntries = data ? Object.entries(data.built_in).sort(([a], [b]) => a.localeCompare(b)) : [];

  return (
    <div className="space-y-5 pb-4">
      {/* Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Errore</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {success && (
        <Alert className="bg-green-50 text-green-700 border-green-200">
          <Save className="h-4 w-4" />
          <AlertTitle>Salvato</AlertTitle>
          <AlertDescription>Acronimi personalizzati aggiornati correttamente.</AlertDescription>
        </Alert>
      )}

      {/* Custom acronyms */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Pencil className="h-4 w-4 text-primary" />
                Acronimi personalizzati
              </CardTitle>
              <CardDescription className="text-xs mt-1">
                Definisci le tue sigle. Hanno priorità sugli acronimi integrati in caso di conflitto.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={load} disabled={isLoading}>
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              </Button>
              <Button size="sm" onClick={handleSave} disabled={isSaving}>
                {isSaving ? (
                  <RefreshCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Save className="h-3.5 w-3.5 mr-1.5" />
                )}
                {isSaving ? "Salvataggio..." : "Salva"}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Add new row */}
          <div className="flex gap-2">
            <Input
              placeholder="Sigla (es. MES)"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              className="w-28 font-mono text-sm uppercase"
              maxLength={12}
            />
            <Input
              placeholder="Espansione semantica (es. Meccanismo Europeo Stabilità fondo salvataggio stati)"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              className="flex-1 text-sm"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleAdd}
              disabled={!newKey.trim() || !newValue.trim()}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          {/* Custom list */}
          {customEntries.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              Nessun acronimo personalizzato. Aggiungine uno sopra.
            </p>
          ) : (
            <div className="rounded-md border divide-y">
              {customEntries.map(([key, value]) => (
                <div key={key} className="flex items-center gap-2 px-3 py-2">
                  <Badge variant="secondary" className="font-mono shrink-0 text-xs">
                    {key}
                  </Badge>
                  {editingKey === key ? (
                    <Input
                      value={editingValue}
                      onChange={(e) => setEditingValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleConfirmEdit();
                        if (e.key === "Escape") setEditingKey(null);
                      }}
                      className="flex-1 h-7 text-xs"
                      autoFocus
                    />
                  ) : (
                    <span
                      className="flex-1 text-xs text-muted-foreground truncate cursor-pointer hover:text-foreground"
                      onClick={() => handleStartEdit(key, value)}
                      title={value}
                    >
                      {value}
                    </span>
                  )}
                  <div className="flex gap-1 shrink-0">
                    {editingKey === key ? (
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleConfirmEdit}>
                        OK
                      </Button>
                    ) : (
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleStartEdit(key, value)}>
                        <Pencil className="h-3 w-3" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      onClick={() => handleDelete(key)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Built-in acronyms (read-only) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            Acronimi integrati
            <Badge variant="outline" className="text-xs font-normal ml-1">
              {builtInEntries.length} voci · sola lettura
            </Badge>
          </CardTitle>
          <CardDescription className="text-xs">
            Dizionario parlamentare italiano incluso nel sistema. Non modificabili dall&apos;interfaccia.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-4">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <ScrollArea className="h-64">
              <div className="rounded-md border divide-y">
                {builtInEntries.map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2 px-3 py-2 opacity-70">
                    <Badge variant="outline" className="font-mono shrink-0 text-xs">
                      {key}
                    </Badge>
                    <span className="flex-1 text-xs text-muted-foreground truncate" title={value}>
                      {value}
                    </span>
                    <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Info box */}
      <div className="rounded-md bg-muted/40 border px-4 py-3 text-xs text-muted-foreground space-y-1">
        <p className="font-medium text-foreground">Come funziona</p>
        <p>
          Quando l&apos;utente cerca <span className="font-mono bg-muted px-1 rounded">SSN</span>,
          il sistema espande automaticamente la sigla con la sua forma estesa e termini correlati
          prima di generare l&apos;embedding — migliorando il retrieval semantico.
        </p>
        <p>
          Per query brevi (≤ 5 parole) viene usato anche un LLM leggero (gpt-4o-mini) per
          arricchire ulteriormente la query. La query originale resta invariata per la ricerca
          lessicale sul grafo.
        </p>
      </div>
    </div>
  );
}
