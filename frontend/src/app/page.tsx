"use client";

import { useState, useEffect } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { ChatArea } from "@/components/chat";
import { HistoryModal } from "@/components/shared/HistoryModal";
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
  const [historyOpen, setHistoryOpen] = useState(false);

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
    <div className="flex h-screen overflow-hidden bg-background w-full max-w-[100vw]">
      {/* Sidebar */}
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={toggle}
        isQueryRunning={isLoading}
        isMobile={isMobile}
        isMobileOpen={isMobileOpen}
        onCloseMobile={closeMobile}
      />
      <HistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} onLoadChat={loadChat} />

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          progress={progress}
          lastCompletedProgress={lastCompletedProgress}
          onSendMessage={sendMessage}
          onCancelRequest={cancelRequest}
          onOpenHistory={() => setHistoryOpen(true)}
          mobileMenuButton={<MobileMenuButton onClick={toggle} />}
        />
      </main>
    </div>
  );
}
