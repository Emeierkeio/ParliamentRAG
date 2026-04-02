"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function RankingRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/rankings");
  }, [router]);
  return null;
}
