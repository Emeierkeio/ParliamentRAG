import type { MetadataRoute } from "next";
import { SITO } from "@/sito/rotte";

export default function robots(): MetadataRoute.Robots {
  // NOINDEX=1: anteprima, da non indicizzare
  if (process.env.NOINDEX === "1") return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: { userAgent: "*", allow: "/", disallow: "/api/" },
    sitemap: `${SITO}/sitemap.xml`,
  };
}
