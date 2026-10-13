// /en/research: pagina «ricerca» (en). Contenuto in src/sito/pagine.ts.
import { servi } from "@/sito/pagine";

export const dynamic = "force-static";
export const GET = () => servi("ricerca", "en");
