import { redirect } from "next/navigation";

// /timeline è il vecchio percorso dei Lavori d'Aula: ora vivono su /sedute
export default function TimelineRedirect() {
  redirect("/sedute");
}
