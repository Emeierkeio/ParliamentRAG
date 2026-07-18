"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
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
import { Settings, RefreshCw, Save, AlertCircle, Info } from "lucide-react";
import { getConfig, reloadConfig, updateConfig } from "@/lib/api";
import type { SystemConfig, ConfigUpdate } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";

import {
  RetrievalEditor,
  AuthorityEditor,
  GenerationEditor,
  QueryRewritingEditor,
} from "./GraphicalEditors";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const t = useTranslations("Settings");
  const [configData, setConfigData] = useState<SystemConfig | null>(null);
  const [originalData, setOriginalData] = useState<SystemConfig | null>(null);
  const [jsonContent, setJsonContent] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const hasUnsavedChanges =
    configData !== null &&
    originalData !== null &&
    JSON.stringify(configData) !== JSON.stringify(originalData);

  const loadConfig = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getConfig();
      setConfigData(data);
      setOriginalData(data);
      setJsonContent(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("loadError"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleReload = async () => {
    setIsLoading(true);
    setError(null);
    setSuccess(false);
    try {
      const data = await reloadConfig();
      setConfigData(data);
      setOriginalData(data);
      setJsonContent(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("reloadError"));
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
        query_rewriting: configData.query_rewriting,
      };
      const updated = await updateConfig(payload);
      setConfigData(updated);
      setOriginalData(updated);
      setJsonContent(JSON.stringify(updated, null, 2));
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveError"));
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
        throw new Error(t("invalidJson"));
      }
      const payload: ConfigUpdate = {
        retrieval: parsed.retrieval,
        authority: parsed.authority,
        generation: parsed.generation,
        query_rewriting: parsed.query_rewriting,
      };
      const updated = await updateConfig(payload);
      setConfigData(updated);
      setOriginalData(updated);
      setJsonContent(JSON.stringify(updated, null, 2));
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveError"));
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
            {t("title")}
            {hasUnsavedChanges && (
              <Badge variant="outline" className="text-xs font-normal text-amber-600 border-amber-300 bg-amber-50 dark:bg-amber-950 ml-1">
                {t("unsavedChanges")}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription className="flex items-center gap-1.5">
            <Info className="h-3.5 w-3.5 shrink-0" />
            {t("description")}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col gap-3 py-1">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{t("error")}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {success && (
            <Alert className="bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-400 dark:border-green-800">
              <Save className="h-4 w-4" />
              <AlertTitle>{t("saved")}</AlertTitle>
              <AlertDescription>{t("savedMessage")}</AlertDescription>
            </Alert>
          )}

          <Tabs defaultValue="visual" className="flex-1 flex flex-col min-h-0">
            <TabsList className="shrink-0">
              <TabsTrigger value="visual">{t("visualEditor")}</TabsTrigger>
              <TabsTrigger value="json">{t("jsonEditor")}</TabsTrigger>
            </TabsList>

            <TabsContent
              value="visual"
              className="flex-1 min-h-0 overflow-y-auto rounded-md border p-4 bg-muted/10 mt-2"
            >
              {configData ? (
                <div className="space-y-4 pb-4">
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
                  <QueryRewritingEditor
                    data={configData.query_rewriting}
                    onChange={(query_rewriting) => setConfigData({ ...configData, query_rewriting })}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              )}
            </TabsContent>

            <TabsContent value="json" className="flex-1 min-h-0 relative border rounded-md mt-2">
              <div className="absolute inset-0 flex flex-col">
                <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/20">
                  <span className="text-xs text-muted-foreground font-mono">{t("configFile")}</span>
                  <Button size="sm" variant="ghost" onClick={handleJsonSave} disabled={isLoading} className="h-6 text-xs">
                    <Save className="h-3 w-3 mr-1" />
                    {t("applyJson")}
                  </Button>
                </div>
                <Textarea
                  value={jsonContent}
                  onChange={(e) => setJsonContent(e.target.value)}
                  className="flex-1 font-mono text-xs resize-none border-0 rounded-none focus-visible:ring-0 p-3"
                  placeholder={t("loadingConfig")}
                  disabled={isLoading}
                />
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <DialogFooter className="gap-2 sm:gap-0 shrink-0">
          <div className="flex-1 flex justify-start">
            <Button variant="outline" size="sm" onClick={handleReload} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
              {t("reloadYaml")}
            </Button>
          </div>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            {t("cancel")}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isLoading || !hasUnsavedChanges}
            className={hasUnsavedChanges ? "" : "opacity-50"}
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                {t("saving")}
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                {t("saveChanges")}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
