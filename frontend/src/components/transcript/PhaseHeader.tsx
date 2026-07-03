interface PhaseHeaderProps {
  id: string;
  title: string;
}

/** Strip leading/trailing parentheses from phase titles like "(Parere del Governo)" */
function cleanTitle(title: string): string {
  return title.replace(/^\(/, "").replace(/\)$/, "").trim();
}

export function PhaseHeader({ id, title }: PhaseHeaderProps) {
  return (
    <div
      data-phase-id={id}
      className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border/60 px-4 py-2 mt-4 first:mt-0"
    >
      <h3 className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
        {cleanTitle(title)}
      </h3>
    </div>
  );
}
