"use client";

import Image from "next/image";
import { getGroupColor, getGroupLogo } from "@/config";

/** Party logo (Wikipedia infobox art, served from /public/groups).
    Groups without a logo fall back to the group-color dot. */
export function GroupLogo({
  group,
  size = 18,
  className = "",
}: {
  group: string;
  size?: number;
  className?: string;
}) {
  const src = getGroupLogo(group);
  if (!src) {
    return (
      <span
        className={`inline-block shrink-0 rounded-full ${className}`}
        style={{
          width: Math.round(size * 0.55),
          height: Math.round(size * 0.55),
          backgroundColor: getGroupColor(group),
        }}
        aria-hidden="true"
      />
    );
  }
  return (
    <Image
      src={src}
      alt=""
      width={size}
      height={size}
      className={`shrink-0 object-contain ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    />
  );
}
