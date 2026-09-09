import { redirect } from "next/navigation";

// /method was the pre-redesign methodology page: it now lives on /metodologia
export default function MethodRedirect() {
  redirect("/metodologia");
}
