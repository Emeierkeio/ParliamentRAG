/*
 * Qualsiasi indirizzo senza una pagina: 404 con la pagina «non trovata»,
 * in inglese sotto /en. Dinamica, così gli indirizzi a caso non finiscono
 * nella cache del server.
 */
import { nonTrovata } from "@/sito/pagine";
import { rispondi } from "@/sito/guscio";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ resto: string[] }> }) {
  const { resto } = await params;
  return rispondi(nonTrovata(resto[0] === "en" ? "en" : "it"), 404);
}
