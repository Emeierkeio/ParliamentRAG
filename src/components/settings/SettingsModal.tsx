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
import { Settings, RefreshCw, Save, AlertCircle, Info } from "lucide-react";
import { getConfig, reloadConfig, updateConfig } from "@/lib/api";
import type { SystemConfig, ConfigUpdate } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
      <DialogContent className="max-w-[95vw] sm:max-w-4xl h-[92dvh] sm:h-[85vh] flex flex-col p-4 sm:p-6 gap-3 sm:gap-4">
        <DialogHeader className="shrink-0">
          <DialogTitle className="[font-family:var(--font-display)] flex items-center gap-2 text-lg font-semibold tracking-tight">
            <Settings className="h-5 w-5 text-primary" />
            {t("title")}
            {hasUnsavedChanges && (
              <Badge variant="outline" className="text-xs font-normal text-amber-600 border-amber-300 bg-amber-50 dark:bg-amber-950 ml-1">
                {t("unsavedChanges")}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription className="flex items-start gap-1.5 text-left">
            <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            {t("description")}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col gap-3 min-h-0">
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

          <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain rounded-lg border bg-muted/10 p-3 sm:p-4">
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
          </div>
        </div>

        <DialogFooter className="shrink-0 flex-row flex-wrap items-center gap-2">
          <div className="flex-1 flex justify-start">
            <Button variant="outline" size="sm" onClick={handleReload} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 sm:mr-2 ${isLoading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">{t("reloadYaml")}</span>
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
