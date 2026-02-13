"use client";

import { useEffect } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { ChatArea } from "@/components/chat";
import { useSidebar, useChat } from "@/hooks";

export default function Home() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const {
    messages,
    isLoading,
    progress,
    lastCompletedProgress,
    sendMessage,
    cancelRequest,
    loadChat,
  } = useChat();

  // Load pending chat from history navigation (from other pages)
  useEffect(() => {
    const pending = sessionStorage.getItem("pendingChat");
    if (pending) {
      sessionStorage.removeItem("pendingChat");
      try {
        const data = JSON.parse(pending);
        loadChat(data);
      } catch (err) {
        console.error("Failed to load pending chat:", err);
      }
    }
  }, [loadChat]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={toggle}
        onLoadChat={loadChat}
        isQueryRunning={isLoading}
        isMobile={isMobile}
        isMobileOpen={isMobileOpen}
        onCloseMobile={closeMobile}
      />

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          progress={progress}
          lastCompletedProgress={lastCompletedProgress}
          onSendMessage={sendMessage}
          onCancelRequest={cancelRequest}
          mobileMenuButton={<MobileMenuButton onClick={toggle} />}
        />
      </main>
    </div>
  );
}
