import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ParliamentRAG",
    short_name: "ParliamentRAG",
    description:
      "Progetto di ricerca per l'AI sui dibattiti delle istituzioni italiane: tre garanzie per ogni risposta sul Parlamento, dati aperti e un metodo per verificarle.",
    id: "/",
    start_url: "/",
    scope: "/",
    lang: "it",
    display: "standalone",
    // --carta di public/sito/famiglia.css: Android dipinge con questo colore
    // lo splash e il primo fotogramma
    background_color: "#f6f5f1",
    theme_color: "#f6f5f1",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
