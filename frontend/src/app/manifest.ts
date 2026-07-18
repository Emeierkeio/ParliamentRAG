import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ParliamentRAG",
    short_name: "ParliamentRAG",
    description:
      "Risposte bilanciate e verificabili sui dibattiti della Camera dei Deputati, con citazioni testuali dai resoconti stenografici.",
    start_url: "/home",
    display: "standalone",
    background_color: "#FBFAF8",
    theme_color: "#1B3A5C",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
