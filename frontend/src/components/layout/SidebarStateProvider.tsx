"use client";

import { createContext, useContext } from "react";

/**
 * Carries the server-read initial collapsed state (from the sidebarCollapsed
 * cookie) down to useSidebar. This lets SSR render the sidebar already
 * collapsed, eliminating the expand→collapse flash on full page loads
 * (language switches and tool navigations reload the page).
 */
const SidebarInitialContext = createContext<boolean | null>(null);

export function SidebarStateProvider({
  initialCollapsed,
  children,
}: {
  initialCollapsed: boolean | null;
  children: React.ReactNode;
}) {
  return (
    <SidebarInitialContext.Provider value={initialCollapsed}>
      {children}
    </SidebarInitialContext.Provider>
  );
}

export function useInitialCollapsed(): boolean | null {
  return useContext(SidebarInitialContext);
}
