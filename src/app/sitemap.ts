import type { MetadataRoute } from "next";
import { IN_SITEMAP, PERCORSI, SITO } from "@/sito/rotte";

export default function sitemap(): MetadataRoute.Sitemap {
  return IN_SITEMAP.flatMap((id) =>
    (["it", "en"] as const).map((l) => ({
      url: SITO + PERCORSI[id][l],
      changeFrequency: id === "home" || id === "dati" ? ("daily" as const) : ("monthly" as const),
      priority: id === "home" ? 1 : 0.7,
      alternates: { languages: { it: SITO + PERCORSI[id].it, en: SITO + PERCORSI[id].en } },
    })),
  );
}
