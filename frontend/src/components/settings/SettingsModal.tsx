"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Settings, RefreshCw, Save, AlertCircle } from "lucide-react";
import { getConfig, updateConfig } from "@/lib/api";
import type { SystemConfig, ConfigUpdate } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

import { RetrievalEditor, AuthorityEditor, GenerationEditor } from "./GraphicalEditors";
import { AcronymsEditor } from "./AcronymsEditor";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [configData, setConfigData] = useState<SystemConfig | null>(null);
  const [jsonContent, setJsonContent] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState("visual");

  const loadConfig = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getConfig();
      setConfigData(data);
      setJsonContent(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore nel caricamento della configurazione");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadConfig();
      setSuccess(false);
    }
  }, [open]);

  // Sync JSON view when graphical editors change
  useEffect(() => {
    if (configData) {
      setJsonContent(JSON.stringify(configData, null, 2));
    }
  }, [configData]);

  const handleSave = async () => {
    if (!configData) return;
    setIsLoading(true);
    setError(null);
    setSuccess(false);
    try {
      const payload: ConfigUpdate = {
        retrieval: configData.retrieval,
        authority: configData.authority,
        generation: configData.generation,
      };
      const updated = await updateConfig(payload);
      setConfigData(updated);
      setJsonContent(JSON.stringify(updated, null, 2));
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore nel salvataggio");
    } finally {
      setIsLoading(false);
    }
  };

  const handleJsonSave = async () => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);
    try {
      let parsed: any;
      try {
        parsed = JSON.parse(jsonContent);
      } catch {
        throw new Error("Formato JSON non valido. Correggi gli errori di sintassi.");
      }
      const payload: ConfigUpdate = {
        retrieval: parsed.retrieval,
        authority: parsed.authority,
        generation: parsed.generation,
      };
      const updated = await updateConfig(payload);
      setConfigData(updated);
      setJsonContent(JSON.stringify(updated, null, 2));
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore nel salvataggio");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] sm:max-w-4xl h-[90vh] sm:h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-primary" />
            Configurazione Sistema
          </DialogTitle>
          <DialogDescription>
            Modifica i parametri del backend in tempo reale.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col gap-4 py-2">
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
              <AlertTitle>Successo</AlertTitle>
              <AlertDescription>Impostazioni salvate correttamente.</AlertDescription>
            </Alert>
          )}

          <Tabs defaultValue="visual" className="flex-1 flex flex-col" onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="visual">Editor Grafico</TabsTrigger>
              <TabsTrigger value="acronyms">Acronimi</TabsTrigger>
              <TabsTrigger value="json">Editor JSON</TabsTrigger>
              <TabsTrigger value="info">Guida</TabsTrigger>
            </TabsList>

            <TabsContent value="visual" className="h-[calc(90vh-220px)] sm:h-[calc(85vh-200px)] overflow-y-auto rounded-md border p-4 bg-muted/10">
              {configData ? (
                <div className="space-y-6 pb-4">
                  <RetrievalEditor
                    data={configData.retrieval}
                    onChange={(retrieval) => setConfigData({ ...configData, retrieval })}
                  />
                  <AuthorityEditor
                    data={configData.authority}
                    onChange={(authority) => setConfigData({ ...configData, authority })}
                  />
                  <GenerationEditor
                    data={configData.generation}
                    onChange={(generation) => setConfigData({ ...configData, generation })}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              )}
            </TabsContent>

            <TabsContent value="acronyms" className="h-[calc(90vh-220px)] sm:h-[calc(85vh-200px)] overflow-y-auto rounded-md border p-4 bg-muted/10">
              <AcronymsEditor />
            </TabsContent>

            <TabsContent value="json" className="flex-1 min-h-0 relative border rounded-md">
              <Textarea
                value={jsonContent}
                onChange={(e) => setJsonContent(e.target.value)}
                className="w-full h-full font-mono text-xs resize-none border-0 focus-visible:ring-0 p-4"
                placeholder="Caricamento configurazione..."
                disabled={isLoading}
              />
            </TabsContent>

            <TabsContent value="info" className="flex-1 overflow-auto">
              <ScrollArea className="h-full pr-4">
                <div className="space-y-4 p-4 text-sm">
                  <h3 className="font-bold">Struttura della configurazione</h3>

                  <div>
                    <h4 className="font-semibold text-primary">Retrieval</h4>
                    <p className="text-muted-foreground">
                      Parametri per la ricerca: Dense Top-K (quanti chunk recuperare),
                      soglie di similarità, e pesi del merger che bilanciano rilevanza,
                      diversità, copertura e autorevolezza.
                    </p>
                  </div>

                  <Separator />

                  <div>
                    <h4 className="font-semibold text-primary">Authority</h4>
                    <p className="text-muted-foreground">
                      Pesi per il calcolo dello score di autorevolezza dei deputati.
                      La somma dei pesi deve essere circa 1.0.
                      Half-life controlla il decadimento temporale di atti e interventi.
                    </p>
                  </div>

                  <Separator />

                  <div>
                    <h4 className="font-semibold text-primary">Generazione</h4>
                    <p className="text-muted-foreground">
                      Modelli OpenAI usati nelle 3 fasi della pipeline (analisi, scrittura, integrazione).
                      Il toggle &quot;Analisi Trasversale&quot; abilita la sezione convergenze/divergenze.
                    </p>
                  </div>

                  <Separator />

                  <div className="text-xs text-muted-foreground">
                    Le sezioni Compass, Coalizioni e Citation sono di sola lettura
                    e possono essere modificate solo editando direttamente il file YAML.
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <div className="flex-1 flex justify-start">
            {activeTab !== "acronyms" && (
              <Button variant="outline" size="sm" onClick={loadConfig} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
                Ricarica
              </Button>
            )}
          </div>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            {activeTab === "acronyms" ? "Chiudi" : "Annulla"}
          </Button>
          {activeTab !== "acronyms" && (
            <Button onClick={activeTab === "json" ? handleJsonSave : handleSave} disabled={isLoading}>
              {isLoading ? "Salvataggio..." : "Salva Modifiche"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
