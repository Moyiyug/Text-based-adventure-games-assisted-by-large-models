import { useCallback, useState } from "react";
import { Send } from "lucide-react";
import { cn } from "../../lib/utils";

interface MessageInputProps {
  disabled?: boolean;
  streaming?: boolean;
  onSend: (text: string) => void;
}

export function MessageInput({ disabled, streaming, onSend }: MessageInputProps) {
  const [value, setValue] = useState("");

  const send = useCallback(() => {
    const t = value.trim();
    if (!t || disabled || streaming) return;
    onSend(t);
    setValue("");
  }, [value, disabled, streaming, onSend]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="shrink-0 border-t border-border bg-bg-primary/90 px-4 py-3">
      <div
        className={cn(
          "flex items-end gap-2 rounded-lg border border-border bg-bg-secondary p-2",
          "focus-within:border-accent-primary focus-within:ring-2 focus-within:ring-accent-primary/20",
          (disabled || streaming) && "opacity-60"
        )}
      >
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled || streaming}
          placeholder="输入你的行动…（Shift+Enter 换行）"
          rows={2}
          className={cn(
            "max-h-[120px] min-h-[44px] flex-1 resize-y bg-transparent font-ui text-sm text-text-primary placeholder:text-text-secondary",
            "focus:outline-none disabled:cursor-not-allowed"
          )}
        />
        <button
          type="button"
          onClick={send}
          disabled={disabled || streaming || !value.trim()}
          className={cn(
            "mb-0.5 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-primary text-bg-primary transition-colors",
            "hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/30",
            "disabled:cursor-not-allowed disabled:opacity-50"
          )}
          aria-label="发送"
        >
          {streaming ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-bg-primary border-t-transparent" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
