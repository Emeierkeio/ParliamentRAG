import { redirect } from "next/navigation";

/** /atti è solo un alias: la ricerca con filtro "atti" è la pagina vera. */
export default function AttiPage() {
  redirect("/search?doc_type=act");
}
