interface PhaseHeaderProps {
  id: string;
  title: string;
}

export function PhaseHeader({ id, title }: PhaseHeaderProps) {
  return (
    <div data-phase-id={id} className="bg-muted border-l-[3px] border-primary px-4 py-2 mt-6 mb-2 first:mt-0">
      <h3 className="text-lg font-semibold">{title}</h3>
    </div>
  );
}
