"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

type ChamberValue = "camera" | "senato" | "both";

interface ChamberSelectorProps {
  value: ChamberValue;
  onChange: (value: ChamberValue) => void;
}

const OPTIONS: ChamberValue[] = ["camera", "senato", "both"];

export function ChamberSelector({ value, onChange }: ChamberSelectorProps) {
  const t = useTranslations("ChamberSelector");

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">{t("label")}</span>
      <div className="inline-flex rounded-lg border border-border bg-muted p-0.5">
        {OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={cn(
              "px-3 py-1 text-xs font-medium rounded-md transition-colors",
              value === option
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(option)}
          </button>
        ))}
      </div>
    </div>
  );
}
