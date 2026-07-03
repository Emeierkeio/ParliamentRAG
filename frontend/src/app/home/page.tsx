"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { ChatArea } from "@/components/chat";
import { HistoryModal } from "@/components/shared/HistoryModal";
import { useSidebar, useChat } from "@/hooks";

function HomeContent() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const {
    messages,
    isLoading,
    progress,
    lastCompletedProgress,
    chamber,
    setChamber,
    legislature,
    setLegislature,
    sendMessage,
    cancelRequest,
    loadChat,
  } = useChat();
  const [historyOpen, setHistoryOpen] = useState(false);
  const searchParams = useSearchParams();
  const autoSentRef = useRef(false);

  // Auto-send query from ?q= param (used by timeline "Ask about this")
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !autoSentRef.current && !isLoading && messages.length === 0) {
      autoSentRef.current = true;
      // Clear the ?q= from URL without reload
      window.history.replaceState({}, "", "/home");
      sendMessage(q);
    }
  }, [searchParams, sendMessage, isLoading, messages.length]);

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
        isQueuing={progress?.isWaiting}
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
          chamber={chamber}
          onChamberChange={setChamber}
          legislature={legislature}
          onLegislatureChange={setLegislature}
        />
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={null}>
      <HomeContent />
    </Suspense>
  );
}
