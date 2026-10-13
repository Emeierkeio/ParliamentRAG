// /en: pagina «home» (en). Contenuto in src/sito/pagine.ts.
import { servi } from "@/sito/pagine";

export const dynamic = "force-static";
export const GET = () => servi("home", "en");
