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
import { getSettings, updateSettings } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

import { WeightsEditor, ManualAuthoritiesEditor } from "./GraphicalEditors";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [jsonContent, setJsonContent] = useState("");
  const [parsedConfig, setParsedConfig] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const loadSettings = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSettings();
      setParsedConfig(data);
      setJsonContent(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore nel caricamento delle impostazioni");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadSettings();
      setSuccess(false);
    }
  }, [open]);

  const handleSave = async (dataToSave?: any) => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);
    try {
        let payload = dataToSave;
        
        if (!payload) {
             // Validate JSON from text area
            try {
                payload = JSON.parse(jsonContent);
            } catch (e) {
                throw new Error("Formato JSON non valido. Correggi gli errori di sintassi.");
            }
        }

      const updated = await updateSettings(payload);
      setParsedConfig(updated);
      setJsonContent(JSON.stringify(updated, null, 2)); // Sync JSON view
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore nel salvataggio");
    } finally {
      setIsLoading(false);
    }
  };

  const handleWeightsChange = (newWeights: any) => {
      const newConfig = { ...parsedConfig, AUTHORITY_WEIGHTS: newWeights };
      setParsedConfig(newConfig);
      setJsonContent(JSON.stringify(newConfig, null, 2));
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[85vh] flex flex-col">
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

            <Tabs defaultValue="visual" className="flex-1 flex flex-col">
                <TabsList>
                    <TabsTrigger value="visual">Editor Grafico</TabsTrigger>
                    <TabsTrigger value="json">Editor JSON Avanzato</TabsTrigger>
                    <TabsTrigger value="info">Guida</TabsTrigger>
                </TabsList>
                
                <TabsContent value="visual" className="h-[calc(85vh-180px)] overflow-y-auto rounded-md border p-4 bg-muted/10">
                    {parsedConfig ? (
                        <div className="space-y-6 pb-4">
                            <WeightsEditor 
                                weights={parsedConfig.AUTHORITY_WEIGHTS || {}} 
                                onChange={handleWeightsChange} 
                            />
                            
                            <ManualAuthoritiesEditor 
                                authorities={parsedConfig.MANUAL_AUTHORITIES || {}} 
                                onChange={(newAuths) => {
                                    /* Read-only for now in visual mode */
                                }}
                            />
                            
                            <div className="text-xs text-muted-foreground text-center">
                                Per modifiche strutturali (Role Lists, Groups), usa l'editor JSON.
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="json" className="flex-1 min-h-0 relative border rounded-md">
                   <Textarea
                        value={jsonContent}
                        onChange={(e) => {
                            setJsonContent(e.target.value);
                            // Optional: Try parse to update visual state if valid? 
                            // Better skip to avoid sync issues on partial edits.
                        }}
                        className="w-full h-full font-mono text-xs resize-none border-0 focus-visible:ring-0 p-4"
                        placeholder="Caricamento configurazione..."
                        disabled={isLoading}
                    />
                </TabsContent>
                
                <TabsContent value="info" className="flex-1 overflow-auto">
                    <ScrollArea className="h-full pr-4">
                        <div className="space-y-4 p-4 text-sm">
                            <h3 className="font-bold">Struttura del file di configurazione</h3>
                            
                            <div>
                                <h4 className="font-semibold text-primary">MANUAL_AUTHORITIES</h4>
                                <p className="text-muted-foreground">
                                    Override manuale per assegnare un esperto specifico a un gruppo su un determinato tema.
                                </p>
                                <pre className="bg-muted p-2 rounded mt-2 text-xs">
{`"MANUAL_AUTHORITIES": {
  "giustizia": {
    "FI": "ENRICO COSTA" 
  }
}`}
                                </pre>
                            </div>
                            
                            <Separator />
                            
                            <div>
                                <h4 className="font-semibold text-primary">AUTHORITY_WEIGHTS</h4>
                                <p className="text-muted-foreground">
                                    Pesi usati per calcolare lo score di autorità (somma deve essere ~1.0).
                                </p>
                            </div>
                        </div>
                    </ScrollArea>
                </TabsContent>
            </Tabs>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <div className="flex-1 flex justify-start">
            <Button variant="outline" size="sm" onClick={loadSettings} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                Ricarica
            </Button>
          </div>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>Annulla</Button>
          <Button onClick={() => handleSave(parsedConfig)} disabled={isLoading}>
            {isLoading ? "Salvataggio..." : "Salva Modifiche"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
