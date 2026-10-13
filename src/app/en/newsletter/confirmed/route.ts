// /en/newsletter/confirmed: pagina «confermata» (en). Contenuto in src/sito/pagine.ts.
import { servi } from "@/sito/pagine";

export const dynamic = "force-static";
export const GET = () => servi("confermata", "en");
