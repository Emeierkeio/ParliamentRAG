"use client";

import { useState, useCallback } from "react";
import { config } from "@/config";

export function useSidebar() {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(config.ui.sidebar.defaultCollapsed);

  const toggle = useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, []);

  const collapse = useCallback(() => {
    setIsCollapsed(true);
  }, []);

  const expand = useCallback(() => {
    setIsCollapsed(false);
  }, []);

  return {
    isCollapsed,
    toggle,
    collapse,
    expand,
    width: isCollapsed
      ? config.ui.sidebar.width.collapsed
      : config.ui.sidebar.width.expanded,
  };
}
