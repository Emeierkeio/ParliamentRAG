"use client";

import { useState } from "react";

/** 32px foto deputato con fallback alle iniziali quando l'immagine manca o non carica. */
export function GroupMemberAvatar({
  photo,
  name,
}: {
  photo: string | null | undefined;
  name: string;
}) {
  const [errored, setErrored] = useState(false);

  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  if (!photo || errored) {
    return (
      <span
        aria-hidden
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[0.65rem] text-muted-foreground"
      >
        {initials}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={photo}
      alt=""
      loading="lazy"
      onError={() => setErrored(true)}
      className="h-8 w-8 shrink-0 rounded-full object-cover"
    />
  );
}
