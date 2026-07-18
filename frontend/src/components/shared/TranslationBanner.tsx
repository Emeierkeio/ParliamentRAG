"use client";

import { useState, useEffect } from "react";
import { useTranslations, useLocale } from "next-intl";
import { X, Globe } from "lucide-react";

const DISMISS_KEY = "translationBannerDismissed";

interface TranslationBannerProps {
  hasCitations: boolean;
}

export function TranslationBanner({ hasCitations }: TranslationBannerProps) {
  const locale = useLocale();
  const t = useTranslations("TranslationBanner");
  const [dismissed, setDismissed] = useState(true); // Start true to avoid flash

  useEffect(() => {
    setDismissed(localStorage.getItem(DISMISS_KEY) === "true");
  }, []);

  // Only show for non-Italian locale when citations exist
  if (locale === "it" || !hasCitations || dismissed) return null;

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, "true");
    setDismissed(true);
  };

  return (
    <div className="flex items-center gap-2 px-4 py-2 mb-2 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800">
      <Globe className="h-4 w-4 flex-shrink-0" />
      <p className="flex-1">{t("message")}</p>
      <button
        onClick={handleDismiss}
        className="text-xs text-blue-600 hover:text-blue-800 whitespace-nowrap underline"
      >
        {t("dontShowAgain")}
      </button>
      <button
        onClick={() => setDismissed(true)}
        className="p-0.5 hover:bg-blue-100 rounded"
        aria-label="Close"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
