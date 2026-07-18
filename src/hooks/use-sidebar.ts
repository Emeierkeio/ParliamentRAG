"use client";

import { useState, useCallback, useEffect, useLayoutEffect } from "react";
import { config } from "@/config";

const MOBILE_BREAKPOINT = 768;
const COLLAPSED_KEY = "sidebarCollapsed";

export function useSidebar() {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(config.ui.sidebar.defaultCollapsed);
  const [isMobile, setIsMobile] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // Restore the persisted collapsed state before paint, so language switches
  // and tool navigations (full page reloads) don't visually re-open the
  // sidebar. Read in useLayoutEffect (not in the useState initializer) to
  // avoid an SSR hydration mismatch.
  useLayoutEffect(() => {
    const stored = localStorage.getItem(COLLAPSED_KEY);
    if (stored !== null) setIsCollapsed(stored === "true");
  }, []);

  const persist = (value: boolean) => {
    try {
      localStorage.setItem(COLLAPSED_KEY, String(value));
    } catch {
      // Storage unavailable (private mode etc.) — state just won't persist
    }
  };

  useEffect(() => {
    const check = () => {
      const mobile = window.innerWidth < MOBILE_BREAKPOINT;
      setIsMobile(mobile);
      if (mobile) {
        // Mobile always renders collapsed; don't persist this forced value
        setIsCollapsed(true);
        setIsMobileOpen(false);
      }
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const toggle = useCallback(() => {
    if (isMobile) {
      setIsMobileOpen((prev) => !prev);
    } else {
      setIsCollapsed((prev) => {
        persist(!prev);
        return !prev;
      });
    }
  }, [isMobile]);

  const collapse = useCallback(() => {
    setIsCollapsed(true);
    persist(true);
  }, []);

  const expand = useCallback(() => {
    setIsCollapsed(false);
    persist(false);
  }, []);

  const closeMobile = useCallback(() => {
    setIsMobileOpen(false);
  }, []);

  return {
    isCollapsed,
    isMobile,
    isMobileOpen,
    toggle,
    collapse,
    expand,
    closeMobile,
    width: isCollapsed
      ? config.ui.sidebar.width.collapsed
      : config.ui.sidebar.width.expanded,
  };
}
