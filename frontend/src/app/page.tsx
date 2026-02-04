"use client";

import { Sidebar } from "@/components/layout";
import { ChatArea } from "@/components/chat";
import { useSidebar, useChat } from "@/hooks";

export default function Home() {
  const { isCollapsed, toggle } = useSidebar();
  const {
    messages,
    isLoading,
    progress,
    sendMessage,
    cancelRequest,
    loadChat,
  } = useChat();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar isCollapsed={isCollapsed} onToggle={toggle} onLoadChat={loadChat} />

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          progress={progress}
          onSendMessage={sendMessage}
          onCancelRequest={cancelRequest}
        />
      </main>
    </div>
  );
}
