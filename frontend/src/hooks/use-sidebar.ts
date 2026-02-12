"use client";

import { useState, useCallback, useEffect } from "react";
import { config } from "@/config";

const MOBILE_BREAKPOINT = 768;

export function useSidebar() {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(config.ui.sidebar.defaultCollapsed);
  const [isMobile, setIsMobile] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  useEffect(() => {
    const check = () => {
      const mobile = window.innerWidth < MOBILE_BREAKPOINT;
      setIsMobile(mobile);
      if (mobile) {
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
      setIsCollapsed((prev) => !prev);
    }
  }, [isMobile]);

  const collapse = useCallback(() => {
    setIsCollapsed(true);
  }, []);

  const expand = useCallback(() => {
    setIsCollapsed(false);
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
