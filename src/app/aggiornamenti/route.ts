// /aggiornamenti: pagina «aggiornamenti» (it). Contenuto in src/sito/pagine.ts.
import { servi } from "@/sito/pagine";

export const dynamic = "force-static";
export const GET = () => servi("aggiornamenti", "it");
