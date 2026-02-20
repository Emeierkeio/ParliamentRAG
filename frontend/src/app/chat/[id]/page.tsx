"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { ChatArea } from "@/components/chat";
import { useSidebar, useChat } from "@/hooks";
import { config } from "@/config";
import { Loader2 } from "lucide-react";

export default function SharedChatPage() {
  const params = useParams();
  const chatId = params.id as string;
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

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chatId) return;

    const fetchChat = async () => {
      try {
        const res = await fetch(`${config.api.baseUrl}/history/${chatId}`);
        if (!res.ok) {
          setError("Conversazione non trovata");
          return;
        }
        const data = await res.json();
        loadChat(data);
      } catch {
        setError("Errore nel caricamento della conversazione");
      } finally {
        setLoading(false);
      }
    };

    fetchChat();
  }, [chatId, loadChat]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Caricamento conversazione...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center">
          <p className="text-lg font-medium text-foreground mb-2">{error}</p>
          <a href="/" className="text-sm text-primary hover:underline">
            Torna alla home
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background w-full max-w-[100vw]">
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={toggle}
        isQueryRunning={isLoading}
        isMobile={isMobile}
        isMobileOpen={isMobileOpen}
        onCloseMobile={closeMobile}
      />
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
