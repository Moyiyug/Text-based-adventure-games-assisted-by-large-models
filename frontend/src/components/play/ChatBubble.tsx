import { useState } from "react";
import { ChevronDown, MessageCircle, MessageSquare } from "lucide-react";
import {
  formatPlainChoiceLabel,
  stripMetaSuffixForDisplay,
} from "../../lib/narrativeDisplay";
import { cn } from "../../lib/utils";
import { useAuthStore } from "../../stores/authStore";
import { coerceChoicesFromMetadata } from "../../stores/sessionStore";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  /** 真实消息 id（>0）时可显示反馈入口 */
  messageId?: number;
  /** 服务端落库的 metadata（管理员调试折叠内展示） */
  metadata?: Record<string, unknown>;
  onFeedbackClick?: (messageId: number) => void;
}

export function ChatBubble({
  role,
  content,
  streaming,
  messageId,
  metadata,
  onFeedbackClick,
}: ChatBubbleProps) {
  const isGm = role === "assistant";
  /** 已落库且 metadata 有 ≥2 条结构化选项时，才从气泡去掉文末编号，避免与底部按钮重复；否则保留正文编号作兜底阅读。流式/临时 id 不去编号，以免未完成流时误剥。 */
  const stripNumberedTail =
    isGm &&
    !streaming &&
    messageId != null &&
    messageId > 0 &&
    coerceChoicesFromMetadata(metadata).length >= 2;
  const strippedGm = isGm
    ? stripMetaSuffixForDisplay(content, {
        stripNumberedTail,
        streaming: Boolean(streaming),
      })
    : content;
  const displayContent = isGm
    ? strippedGm
    : formatPlainChoiceLabel(content);
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  const [debugOpen, setDebugOpen] = useState(false);
  const contentMatchesDisplay =
    isGm && content.trim() === strippedGm.trim();
  const showAdminDebug =
    isGm &&
    isAdmin &&
    !streaming &&
    messageId != null &&
    messageId > 0 &&
    content.trim().length > 0;
  const metadataJson =
    metadata && Object.keys(metadata).length > 0
      ? JSON.stringify(metadata, null, 2)
      : "";

  return (
    <div
      className={cn(
        "flex w-full gap-3",
        isGm ? "justify-start" : "justify-end"
      )}
    >
      {isGm && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-bg-hover text-accent-primary">
          <MessageSquare className="h-4 w-4" />
        </div>
      )}
      <div
        className={cn(
          "relative max-w-[min(100%,720px)] rounded-2xl px-4 py-3",
          isGm
            ? "border-l-[3px] border-accent-primary bg-bg-secondary"
            : "bg-bg-hover"
        )}
      >
        {isGm && (
          <div className="mb-1 font-ui text-xs font-medium text-text-secondary">
            旁白
          </div>
        )}
        <p
          className={cn(
            "whitespace-pre-wrap text-base leading-[1.8]",
            isGm ? "font-story text-gm-text" : "font-ui text-player-text"
          )}
        >
          {displayContent}
          {streaming && (
            <span className="ml-0.5 inline-block h-4 w-1 animate-pulse bg-accent-primary align-middle" />
          )}
        </p>
        {showAdminDebug && (
          <div className="mt-3 border-t border-border pt-2">
            <button
              type="button"
              onClick={() => setDebugOpen((o) => !o)}
              className="flex w-full items-center justify-between rounded-md px-2 py-1.5 font-ui text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-accent-primary"
              aria-expanded={debugOpen}
            >
              <span>协议原文（调试，仅管理员）</span>
              <ChevronDown
                className={cn("h-4 w-4 transition-transform", debugOpen && "rotate-180")}
              />
            </button>
            {debugOpen && (
              <div className="mt-2 space-y-3">
                {contentMatchesDisplay && (
                  <p className="rounded-md bg-bg-primary px-2 py-1 font-ui text-xs text-text-secondary">
                    与服务端存储一致（已剥离 META 分隔段）。
                  </p>
                )}
                <div>
                  <div className="mb-1 font-ui text-xs font-medium text-text-secondary">
                    落库正文
                  </div>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-md bg-bg-primary p-2 font-mono text-xs leading-relaxed text-text-secondary">
                    {content}
                  </pre>
                </div>
                {metadataJson ? (
                  <div>
                    <div className="mb-1 font-ui text-xs font-medium text-text-secondary">
                      metadata（调试）
                    </div>
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-md bg-bg-primary p-2 font-mono text-xs leading-relaxed text-text-secondary">
                      {metadataJson}
                    </pre>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}
        {isGm &&
          messageId != null &&
          messageId > 0 &&
          onFeedbackClick &&
          !streaming && (
            <button
              type="button"
              onClick={() => onFeedbackClick(messageId)}
              className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 font-ui text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-accent-primary"
              aria-label="反馈本条叙事"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              反馈
            </button>
          )}
      </div>
    </div>
  );
}
