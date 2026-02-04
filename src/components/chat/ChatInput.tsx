"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { config } from "@/config";
import { Send, Square, Loader2, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string, mode: "standard" | "high_quality") => void;
  onCancel?: () => void;
  isLoading?: boolean;
  isHighQuality?: boolean;
  onToggleHighQuality?: () => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  onCancel,
  isLoading = false,
  isHighQuality = false,
  onToggleHighQuality,
  disabled = false,
  className,
  placeholder,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (trimmed && !disabled && !isLoading) {
      onSend(trimmed, isHighQuality ? "high_quality" : "standard");
      setValue("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleCancel = () => {
    onCancel?.();
  };

  const charCount = value.length;
  const isNearLimit = charCount > config.ui.chat.maxMessageLength * 0.9;
  const isOverLimit = charCount > config.ui.chat.maxMessageLength;

  return (
    <div className={cn("relative", className)}>
      <div className="group relative rounded-2xl border border-border bg-background focus-within:ring-2 focus-within:ring-primary/20 shadow-sm transition-all hover:border-primary/50">
        <div className="flex items-center min-h-[48px] pr-2 gap-2">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || config.ui.chat.placeholder}
            disabled={disabled}
            rows={1}
            className={cn(
              "flex-1 resize-none bg-transparent px-4 py-3 text-base text-foreground placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed disabled:opacity-50",
              "scrollbar-thin max-h-[200px]"
            )}
          />

          {/* High Quality Toggle */}
          {!isLoading && (
            <Button
              size="icon"
              variant="ghost" 
              onClick={() => onToggleHighQuality?.()}
              title={isHighQuality ? "Deep Search Attivo (Best-of-N)" : "Attiva Deep Search"}
              className={cn(
                "h-8 w-8 shrink-0 rounded-lg transition-all",
                isHighQuality ? "text-primary bg-primary/10 hover:bg-primary/20" : "text-muted-foreground hover:bg-muted"
              )}
            >
              <Sparkles className="h-4 w-4" />
            </Button>
          )}

          {/* Action button */}
          {isLoading ? (
            <Button
              size="icon"
              variant="destructive"
              onClick={handleCancel}
              className="h-9 w-9 shrink-0 rounded-xl"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={handleSubmit}
              disabled={disabled || !value.trim() || isOverLimit}
              className={cn(
                "h-9 w-9 shrink-0 rounded-xl transition-all",
                value.trim() ? "opacity-100 scale-100" : "opacity-0 scale-90 w-0 h-0 p-0 overflow-hidden" 
              )}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Character count - Absolute position to avoid layout shifts, only show when near limit */}
        {value.length > config.ui.chat.maxMessageLength * 0.8 && (
          <div className="absolute bottom-1 right-4">
            <span
              className={cn(
                "text-[10px] transition-colors bg-background/80 px-1 rounded",
                isOverLimit
                  ? "text-destructive font-medium"
                  : isNearLimit
                  ? "text-yellow-500"
                  : "text-muted-foreground"
              )}
            >
              {charCount}/{config.ui.chat.maxMessageLength}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
