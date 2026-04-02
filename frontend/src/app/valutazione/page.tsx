"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ValutazioneRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/evaluation");
  }, [router]);
  return null;
}
