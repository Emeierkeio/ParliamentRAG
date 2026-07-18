"use client";

import { useState, useCallback, useEffect } from "react";
import { config } from "@/config";
import { useInitialCollapsed } from "@/components/layout/SidebarStateProvider";

const MOBILE_BREAKPOINT = 768;
const COLLAPSED_COOKIE = "sidebarCollapsed";

export function useSidebar() {
  // The initial collapsed state is read server-side from the sidebarCollapsed
  // cookie (see layout.tsx → SidebarStateProvider), so SSR already renders the
  // sidebar in the right state: no expand→collapse flash on full page loads
  // (language switches and tool navigations reload the page).
  const initialCollapsed = useInitialCollapsed();
  const [isCollapsed, setIsCollapsed] = useState<boolean>(
    initialCollapsed ?? config.ui.sidebar.defaultCollapsed
  );
  const [isMobile, setIsMobile] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const persist = (value: boolean) => {
    document.cookie = `${COLLAPSED_COOKIE}=${value}; path=/; max-age=31536000; SameSite=Lax`;
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
