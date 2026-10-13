// /en/updates: pagina «aggiornamenti» (en). Contenuto in src/sito/pagine.ts.
import { servi } from "@/sito/pagine";

export const dynamic = "force-static";
export const GET = () => servi("aggiornamenti", "en");
