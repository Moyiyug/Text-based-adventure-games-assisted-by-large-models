import { useAuthStore } from "../stores/authStore";

export interface CompletionPayload {
  reason: string;
  summary: string;
  narrative_status: string;
}

export interface SSEEventHandlers {
  onToken?: (content: string) => void;
  onChoices?: (choices: string[]) => void;
  onStateUpdate?: (state: Record<string, unknown>) => void;
  /** Phase 11：终局回合，在 choices 之前收到（与 BACKEND_STRUCTURE §4.4.2 一致） */
  onCompletion?: (payload: CompletionPayload) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
}

interface SSEPayload {
  type?: string;
  content?: string;
  choices?: string[];
  state?: Record<string, unknown>;
  message?: string;
  reason?: string;
  summary?: string;
  narrative_status?: string;
}

/** 供单测与流式解析复用 */
export function dispatchSsePayload(
  ev: SSEPayload,
  handlers: SSEEventHandlers
): void {
  switch (ev.type) {
    case "token":
      if (ev.content) handlers.onToken?.(ev.content);
      break;
    case "choices":
      handlers.onChoices?.(ev.choices ?? []);
      break;
    case "state_update":
      if (ev.state && typeof ev.state === "object") {
        handlers.onStateUpdate?.(ev.state);
      }
      break;
    case "completion":
      handlers.onCompletion?.({
        reason: typeof ev.reason === "string" ? ev.reason : "",
        summary: typeof ev.summary === "string" ? ev.summary : "",
        narrative_status:
          typeof ev.narrative_status === "string" ? ev.narrative_status : "completed",
      });
      break;
    case "error":
      handlers.onError?.(
        typeof ev.message === "string" ? ev.message : "生成出错"
      );
      break;
    case "done":
      handlers.onDone?.();
      break;
    default:
      break;
  }
}

/**
 * POST /api/sessions/:id/messages 的 SSE 解析（fetch + ReadableStream）。
 * 禁止 EventSource（见 RULES.md §5.1）。
 */
export async function streamSessionMessage(
  sessionId: number,
  content: string,
  handlers: SSEEventHandlers,
  options?: { signal?: AbortSignal }
): Promise<void> {
  const token = useAuthStore.getState().token;
  if (!token) {
    handlers.onError?.("未登录");
    handlers.onDone?.();
    return;
  }

  const res = await fetch(`/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ content }),
    signal: options?.signal,
  });

  if (res.status === 401) {
    useAuthStore.getState().logout();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    handlers.onDone?.();
    return;
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    handlers.onError?.(text.slice(0, 500) || `请求失败 (${res.status})`);
    handlers.onDone?.();
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    handlers.onError?.("无法读取响应流");
    handlers.onDone?.();
    return;
  }

  const decoder = new TextDecoder();
  let carry = "";
  let doneCalled = false;
  const fireDone = () => {
    if (!doneCalled) {
      doneCalled = true;
      handlers.onDone?.();
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      carry += decoder.decode(value, { stream: !done });
      const lines = carry.split("\n");
      carry = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const raw = trimmed.slice(5).trim();
        let ev: SSEPayload;
        try {
          ev = JSON.parse(raw) as SSEPayload;
        } catch {
          continue;
        }
        if (ev.type === "done") {
          fireDone();
        } else {
          dispatchSsePayload(ev, {
            ...handlers,
            onDone: undefined,
          });
        }
      }

      if (done) break;
    }
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      fireDone();
      return;
    }
    handlers.onError?.((e as Error).message || "流式连接中断");
  } finally {
    fireDone();
  }
}
