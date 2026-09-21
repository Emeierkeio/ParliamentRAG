"use client";

import { useTranslations } from "next-intl";
import { Check, ChevronDown, Info, Landmark } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

// Rows are plain divs, not options: the corpus is a single (chamber,
// legislature) pair today, and the popover exists to state that scope
// explicitly and to reserve the spot where the real selector will land.
function ScopeRow({
  label,
  sub,
  active,
  soonLabel,
}: {
  label: string;
  sub?: string;
  active?: boolean;
  soonLabel?: string;
}) {
  return (
    <div
      aria-disabled={!active || undefined}
      className={cn(
        "flex items-center justify-between gap-3 rounded-md px-2.5 py-2",
        active ? "bg-primary/5" : "opacity-70"
      )}
    >
      <div className="min-w-0">
        <p
          className={cn(
            "text-sm leading-snug",
            active ? "font-medium text-foreground" : "text-muted-foreground"
          )}
        >
          {label}
        </p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
      {active ? (
        <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
      ) : (
        soonLabel && (
          <span className="shrink-0 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
            {soonLabel}
          </span>
        )
      )}
    </div>
  );
}

export function ScopePicker({
  variant = "hero",
}: {
  /** "hero" is the welcome-screen eyebrow: selector affordance (chevron,
      option rows) because the scope will become choosable there. "meta"
      sits in a report metadata row where the answer is already built on a
      fixed corpus, so it must read as provenance: Info icon, no option
      rows, plain disclosure text. */
  variant?: "hero" | "meta";
}) {
  const t = useTranslations("WelcomeScreen");
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          aria-label={t("scopeAria")}
          className={cn(
            "group inline-flex items-center rounded-full border border-border text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer",
            variant === "hero"
              ? "gap-2 px-3.5 py-1.5 text-[11px] uppercase tracking-[0.2em]"
              : "gap-1.5 px-2.5 py-0.5 text-xs font-medium"
          )}
        >
          <Landmark
            className={variant === "hero" ? "h-3.5 w-3.5" : "h-3 w-3"}
            aria-hidden="true"
          />
          {t("badge")}
          {variant === "hero" ? (
            <ChevronDown
              className="h-3 w-3 opacity-60 transition-transform group-data-[state=open]:rotate-180"
              aria-hidden="true"
            />
          ) : (
            <Info className="h-3 w-3 opacity-60" aria-hidden="true" />
          )}
        </button>
      </PopoverTrigger>
      {variant === "hero" ? (
        <PopoverContent
          align="center"
          sideOffset={8}
          className="w-80 overflow-hidden p-0 text-left"
        >
          <div className="px-2 pb-1 pt-2.5">
            <p className="px-2.5 pb-1.5 text-xs font-medium text-muted-foreground">
              {t("scopeBranch")}
            </p>
            <ScopeRow
              active
              label={t("scopeCamera")}
              sub={t("scopeCameraSub")}
            />
            <ScopeRow label={t("scopeSenate")} soonLabel={t("scopeSoon")} />
          </div>
          <div className="px-2 pb-2.5 pt-1.5">
            <p className="px-2.5 pb-1.5 text-xs font-medium text-muted-foreground">
              {t("scopeLegislature")}
            </p>
            <ScopeRow active label={t("scopeLeg19")} sub={t("scopeLeg19Sub")} />
            <ScopeRow label={t("scopeLegPast")} soonLabel={t("scopeSoon")} />
          </div>
          <p className="border-t border-border bg-muted/40 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
            {t("scopeNote")}
          </p>
        </PopoverContent>
      ) : (
        <PopoverContent
          align="start"
          sideOffset={8}
          className="w-72 p-4 text-left"
        >
          <p className="mb-1.5 text-sm font-medium text-foreground">
            {t("scopeMetaTitle")}
          </p>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t("scopeMetaNote")}
          </p>
        </PopoverContent>
      )}
    </Popover>
  );
}
