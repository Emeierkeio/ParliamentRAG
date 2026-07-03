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
    <div className="flex items-center gap-2 shrink-0">
      <span className="hidden md:inline text-[11px] uppercase tracking-[0.2em] text-muted-foreground">{t("label")}</span>
      <div className="inline-flex rounded-none border border-border divide-x divide-border">
        {OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={cn(
              "min-tap-none px-2.5 py-1 text-[11px] sm:text-xs font-medium transition-colors cursor-pointer",
              value === option
                ? "bg-primary text-primary-foreground"
                : "bg-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {t(option)}
          </button>
        ))}
      </div>
    </div>
  );
}
