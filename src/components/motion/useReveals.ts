"use client";

import { useEffect } from "react";
import { startReveals } from "./reveal";

/** Starts the data-reveal engine for the page and stops it on unmount. */
export function useReveals() {
  useEffect(() => startReveals(), []);
}
