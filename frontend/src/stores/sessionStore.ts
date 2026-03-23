import { create } from "zustand";
import type {
  NarrativeState,
  SessionMessage,
  SessionResponse,
} from "../types/session";

/** 游玩页消息（流式中为 true） */
export type UIMessage = SessionMessage & { streaming?: boolean };

interface SessionPlayState {
  sessionId: number | null;
  storyTitle: string | null;
  session: SessionResponse | null;
  messages: UIMessage[];
  latestState: NarrativeState | null;
  choices: string[];
  streaming: boolean;
  parseError: string | null;
  /** 状态面板高亮字段（state_update 变化） */
  stateHighlightKeys: string[];

  resetForSession: () => void;
  resetAndHydrate: (
    sessionId: number,
    session: SessionResponse,
    messages: SessionMessage[],
    narrativeState: NarrativeState | null
  ) => void;
  setStoryTitle: (title: string) => void;
  setMessagesFromServer: (messages: SessionMessage[]) => void;
  addUserMessage: (msg: UIMessage) => void;
  beginAssistantStream: () => void;
  appendStreamToken: (piece: string) => void;
  endAssistantStream: () => void;
  setChoices: (choices: string[]) => void;
  mergeNarrativeState: (partial: Record<string, unknown>) => void;
  /** 回合结束后的完整状态快照（与 SSE state_update 一致） */
  replaceLatestState: (st: NarrativeState) => void;
  setParseError: (msg: string | null) => void;
  setStreaming: (v: boolean) => void;
  clearStateHighlights: () => void;
  /**
   * 从服务端消息列表同步底部选项：最后一条为 user 时清空（等待本轮回复，不沿用过期选项）；
   * 最后一条为 assistant 时用其 metadata.choices（刷新/重进恢复）。
   */
  applyChoicesFromMessages: (messages: SessionMessage[]) => void;
}

const emptyNarrative = (): NarrativeState => ({
  current_location: "",
  active_goal: "",
  important_items: [],
  npc_relations: {},
});

/** 协议为 metadata.choices；兼容历史/偏差数据中的 metadata.options（供气泡展示条件等复用） */
export function coerceChoicesFromMetadata(
  meta: Record<string, unknown> | undefined
): string[] {
  if (!meta || typeof meta !== "object") return [];
  let raw: unknown = meta.choices;
  if (!Array.isArray(raw) || raw.length === 0) {
    raw = meta.options;
  }
  if (!Array.isArray(raw)) return [];
  return raw.map((x) => String(x)).filter((s) => s.length > 0);
}

function diffStateKeys(
  prev: Record<string, unknown>,
  next: Record<string, unknown>
): string[] {
  const keys = new Set([...Object.keys(prev), ...Object.keys(next)]);
  return [...keys].filter(
    (k) => JSON.stringify(prev[k]) !== JSON.stringify(next[k])
  );
}

export const useSessionPlayStore = create<SessionPlayState>((set) => ({
  sessionId: null,
  storyTitle: null,
  session: null,
  messages: [],
  latestState: null,
  choices: [],
  streaming: false,
  parseError: null,
  stateHighlightKeys: [],

  resetForSession: () =>
    set({
      sessionId: null,
      storyTitle: null,
      session: null,
      messages: [],
      latestState: null,
      choices: [],
      streaming: false,
      parseError: null,
      stateHighlightKeys: [],
    }),

  resetAndHydrate: (sessionId, session, messages, narrativeState) =>
    set({
      sessionId,
      session,
      messages: messages.map((m) => ({ ...m })),
      latestState: narrativeState ? { ...narrativeState } : emptyNarrative(),
      /** 选项由 PlaySessionPage 在 hydrate 后立刻调用 applyChoicesFromMessages 填充 */
      choices: [],
      streaming: false,
      parseError: null,
      stateHighlightKeys: [],
    }),

  setStoryTitle: (title) => set({ storyTitle: title }),

  setMessagesFromServer: (messages) =>
    set({
      messages: messages.map((m) => ({ ...m, streaming: false })),
    }),

  addUserMessage: (msg) =>
    set((s) => ({
      messages: [...s.messages, { ...msg, streaming: false }],
    })),

  beginAssistantStream: () =>
    set((s) => {
      const maxT = s.messages.reduce((a, m) => Math.max(a, m.turn_number), 0);
      return {
        streaming: true,
        parseError: null,
        messages: [
          ...s.messages,
          {
            id: -Date.now(),
            turn_number: maxT + 1,
            role: "assistant",
            content: "",
            metadata: {},
            streaming: true,
          },
        ],
      };
    }),

  appendStreamToken: (piece) =>
    set((s) => {
      const msgs = [...s.messages];
      const idx = msgs.length - 1;
      if (idx < 0 || msgs[idx].role !== "assistant" || !msgs[idx].streaming) return s;
      msgs[idx] = {
        ...msgs[idx],
        content: msgs[idx].content + piece,
      };
      return { messages: msgs };
    }),

  endAssistantStream: () =>
    set((s) => {
      const msgs = s.messages.map((m) =>
        m.streaming ? { ...m, streaming: false } : m
      );
      return { messages: msgs, streaming: false };
    }),

  setChoices: (choices) => set({ choices }),

  applyChoicesFromMessages: (messages) =>
    set(() => {
      if (!messages.length) {
        return { choices: [] };
      }
      const last = messages[messages.length - 1];
      if (last.role === "user") {
        return { choices: [] };
      }
      return { choices: coerceChoicesFromMetadata(last.metadata) };
    }),

  mergeNarrativeState: (partial) =>
    set((s) => {
      const prev = { ...(s.latestState ?? emptyNarrative()) } as Record<string, unknown>;
      const next = { ...prev, ...partial } as NarrativeState;
      const keys = Object.keys(partial).filter(
        (k) => JSON.stringify(prev[k]) !== JSON.stringify((next as Record<string, unknown>)[k])
      );
      return {
        latestState: next,
        stateHighlightKeys: keys.length ? keys : s.stateHighlightKeys,
      };
    }),

  replaceLatestState: (st) =>
    set((s) => {
      const prev = (s.latestState ?? emptyNarrative()) as Record<string, unknown>;
      const next = st as Record<string, unknown>;
      return {
        latestState: { ...st },
        stateHighlightKeys: diffStateKeys(prev, next),
      };
    }),

  setParseError: (parseError) => set({ parseError }),

  setStreaming: (streaming) => set({ streaming }),

  clearStateHighlights: () => set({ stateHighlightKeys: [] }),
}));
