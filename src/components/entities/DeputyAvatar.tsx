"use client";

import { useState } from "react";
import { getGroupColor } from "@/config";

interface DeputyAvatarProps {
  photo: string | null;
  firstName: string;
  lastName: string;
  group: string | null;
  /** Diameter in px */
  size: number;
}

/**
 * Foto tonda del deputato con fallback a iniziali tinte del colore
 * del gruppo (le foto camera.it a volte mancano o rispondono 404).
 */
export function DeputyAvatar({ photo, firstName, lastName, group, size }: DeputyAvatarProps) {
  const [failed, setFailed] = useState(false);
  const color = getGroupColor(group ?? "");
  const initials = `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();

  if (!photo || failed) {
    return (
      <span
        aria-hidden="true"
        className="inline-flex shrink-0 select-none items-center justify-center rounded-full font-medium"
        style={{
          width: size,
          height: size,
          backgroundColor: `${color}1f`,
          color,
          fontSize: Math.round(size * 0.34),
        }}
      >
        {initials}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- foto esterne camera.it, serve onError
    <img
      src={photo}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      className="shrink-0 rounded-full bg-muted object-cover"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}
