import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import {
  archiveSession,
  getSession,
  getSessionMessages,
  getSessionState,
  postFeedback,
  postOpening,
  resumeSession,
} from "../api/sessionApi";
import { getStory } from "../api/storyApi";
import type { NarrativeState } from "../types/session";
import { streamSessionMessage } from "../hooks/useSSEStream";
import { useSessionPlayStore } from "../stores/sessionStore";
import { ChatBubble } from "../components/play/ChatBubble";
import { ChoicePanel } from "../components/play/ChoicePanel";
import { ModeBadge } from "../components/play/ModeBadge";
import { StatePanel } from "../components/play/StatePanel";
import { MessageInput } from "../components/play/MessageInput";
import { FeedbackDialog } from "../components/play/FeedbackDialog";
import { Button } from "../components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../components/ui/Dialog";
import { toast, toastApiError } from "../lib/toast";

function normalizeNarrativeState(raw: Record<string, unknown>): NarrativeState {
  return {
    current_location:
      typeof raw.current_location === "string" ? raw.current_location : "",
    active_goal: typeof raw.active_goal === "string" ? raw.active_goal : "",
    important_items: Array.isArray(raw.important_items) ? raw.important_items : [],
    npc_relations:
      raw.npc_relations &&
      typeof raw.npc_relations === "object" &&
      !Array.isArray(raw.npc_relations)
        ? (raw.npc_relations as Record<string, string>)
        : {},
  };
}

/**
 * 进入页后若无助手消息则自动请求开场（幂等：后端 409 时仅刷新消息列表）。
 * 避免与手动流式双请求：此处只调 postOpening，多轮仅走 /messages SSE。
 */
export default function PlaySessionPage() {
  const { sessionId: sessionIdParam } = useParams<{ sessionId: string }>();
  const sessionId = sessionIdParam ? Number(sessionIdParam) : NaN;
  const qc = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const openingHandledRef = useRef<number | null>(null);
  const parseHintShownForMessageId = useRef<number | null>(null);

  const [freeInputMode, setFreeInputMode] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackMessageId, setFeedbackMessageId] = useState<number | null>(null);
  const [archiveDialogOpen, setArchiveDialogOpen] = useState(false);

  const messages = useSessionPlayStore((s) => s.messages);
  const choices = useSessionPlayStore((s) => s.choices);
  const latestState = useSessionPlayStore((s) => s.latestState);
  const streaming = useSessionPlayStore((s) => s.streaming);
  const parseError = useSessionPlayStore((s) => s.parseError);
  const storyTitle = useSessionPlayStore((s) => s.storyTitle);
  const stateHighlightKeys = useSessionPlayStore((s) => s.stateHighlightKeys);

  const resetForSession = useSessionPlayStore((s) => s.resetForSession);
  const resetAndHydrate = useSessionPlayStore((s) => s.resetAndHydrate);
  const setStoryTitle = useSessionPlayStore((s) => s.setStoryTitle);
  const addUserMessage = useSessionPlayStore((s) => s.addUserMessage);
  const beginAssistantStream = useSessionPlayStore((s) => s.beginAssistantStream);
  const appendStreamToken = useSessionPlayStore((s) => s.appendStreamToken);
  const endAssistantStream = useSessionPlayStore((s) => s.endAssistantStream);
  const setChoices = useSessionPlayStore((s) => s.setChoices);
  const replaceLatestState = useSessionPlayStore((s) => s.replaceLatestState);
  const setParseError = useSessionPlayStore((s) => s.setParseError);
  const clearStateHighlights = useSessionPlayStore((s) => s.clearStateHighlights);

  const {
    data: session,
    isLoading: sessionLoading,
    error: sessionError,
  } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId),
    enabled: Number.isFinite(sessionId),
  });

  const { data: messagesData, error: messagesError } = useQuery({
    queryKey: ["sessionMessages", sessionId],
    queryFn: () => getSessionMessages(sessionId),
    enabled: Number.isFinite(sessionId),
  });

  const { data: stateSnap } = useQuery({
    queryKey: ["sessionState", sessionId],
    queryFn: async () => {
      try {
        return await getSessionState(sessionId);
      } catch (e) {
        if (axios.isAxiosError(e) && e.response?.status === 404) return null;
        throw e;
      }
    },
    enabled: Number.isFinite(sessionId),
  });

  const { data: story } = useQuery({
    queryKey: ["story", session?.story_id],
    queryFn: () => getStory(session!.story_id),
    enabled: !!session?.story_id,
  });

  const sessionActive = session?.status === "active";
  const archived = session?.status === "archived";

  const needOpening =
    Number.isFinite(sessionId) &&
    sessionActive &&
    messagesData !== undefined &&
    !messagesData.some((m) => m.role === "assistant");

  const openingQuery = useQuery({
    queryKey: ["sessionOpening", sessionId],
    queryFn: () => postOpening(sessionId),
    enabled: needOpening && sessionActive,
    retry: 1,
    staleTime: Infinity,
  });

  const archiveMut = useMutation({
    mutationFn: () => archiveSession(sessionId),
    onSuccess: async () => {
      toast.success("会话已归档");
      setArchiveDialogOpen(false);
      await qc.invalidateQueries({ queryKey: ["session", sessionId] });
      await qc.invalidateQueries({ queryKey: ["mySessions"] });
    },
    onError: (e) => toastApiError(e, "归档失败"),
  });

  const resumeMut = useMutation({
    mutationFn: () => resumeSession(sessionId),
    onSuccess: async () => {
      toast.success("已恢复，可继续冒险");
      await qc.invalidateQueries({ queryKey: ["session", sessionId] });
      await qc.invalidateQueries({ queryKey: ["mySessions"] });
    },
    onError: (e) => toastApiError(e, "恢复失败"),
  });

  useEffect(() => {
    openingHandledRef.current = null;
  }, [sessionId]);

  useEffect(() => {
    if (sessionError) toastApiError(sessionError, "加载会话失败");
  }, [sessionError]);

  useEffect(() => {
    if (messagesError) toastApiError(messagesError, "加载消息失败");
  }, [messagesError]);

  useEffect(() => {
    if (!openingQuery.isSuccess || !openingQuery.data || !Number.isFinite(sessionId)) return;
    if (openingHandledRef.current === sessionId) return;
    openingHandledRef.current = sessionId;
    if (openingQuery.data.parse_error) {
      toast.error(openingQuery.data.parse_error);
    }
    if (openingQuery.data.choices?.length) {
      useSessionPlayStore.getState().setChoices(openingQuery.data.choices);
    }
    const su = openingQuery.data.state_update;
    if (su && typeof su === "object") {
      useSessionPlayStore
        .getState()
        .replaceLatestState(normalizeNarrativeState(su as Record<string, unknown>));
    }
    void qc.invalidateQueries({ queryKey: ["sessionMessages", sessionId] });
    void qc.invalidateQueries({ queryKey: ["sessionState", sessionId] });
    void qc.invalidateQueries({ queryKey: ["session", sessionId] });
  }, [openingQuery.isSuccess, openingQuery.data, sessionId, qc]);

  useEffect(() => {
    if (!openingQuery.isError || !openingQuery.error || !Number.isFinite(sessionId)) return;
    const err = openingQuery.error;
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      void qc.invalidateQueries({ queryKey: ["sessionMessages", sessionId] });
    } else {
      toastApiError(err, "开场生成失败");
    }
  }, [openingQuery.isError, openingQuery.error, sessionId, qc]);

  useEffect(() => {
    if (!Number.isFinite(sessionId)) return;
    resetForSession();
  }, [sessionId, resetForSession]);

  useEffect(() => {
    if (!session || messagesData === undefined || !Number.isFinite(sessionId)) return;
    if (streaming) return;
    const narrative: NarrativeState | null =
      stateSnap?.state ??
      (session.latest_state?.state as NarrativeState | undefined) ??
      null;
    resetAndHydrate(sessionId, session, messagesData, narrative);
    useSessionPlayStore.getState().applyChoicesFromMessages(messagesData);
  }, [session, messagesData, stateSnap, sessionId, resetAndHydrate, streaming]);

  useEffect(() => {
    if (story?.title) setStoryTitle(story.title);
  }, [story?.title, setStoryTitle]);

  useEffect(() => {
    if (!stateHighlightKeys.length) return;
    const t = window.setTimeout(() => clearStateHighlights(), 2200);
    return () => clearTimeout(t);
  }, [stateHighlightKeys, clearStateHighlights]);

  useEffect(() => {
    abortRef.current = new AbortController();
    return () => {
      abortRef.current?.abort();
    };
  }, [sessionId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  useEffect(() => {
    if (streaming) return;
    if (choices.length > 0) {
      parseHintShownForMessageId.current = null;
      return;
    }
    const last = [...messages]
      .reverse()
      .find((m) => m.role === "assistant" && !m.streaming && m.id > 0);
    if (!last) return;
    const pe = last.metadata?.parse_error;
    if (typeof pe !== "string" || !pe.trim()) return;
    if (parseHintShownForMessageId.current === last.id) return;
    parseHintShownForMessageId.current = last.id;
    toast("本回合选项解析失败，可使用自由输入继续。", {
      duration: 5000,
      id: `parse-hint-${last.id}`,
    });
  }, [messages, choices.length, streaming]);

  const sendUserContent = useCallback(
    async (content: string) => {
      if (!Number.isFinite(sessionId) || streaming || archived) return;
      const trimmed = content.trim();
      if (!trimmed) return;

      const prev = useSessionPlayStore.getState().messages;
      const maxT = prev.reduce((a, m) => Math.max(a, m.turn_number), 0);

      addUserMessage({
        id: -Date.now(),
        turn_number: maxT + 1,
        role: "user",
        content: trimmed,
        metadata: {},
      });
      setChoices([]);
      beginAssistantStream();
      setParseError(null);

      await streamSessionMessage(
        sessionId,
        trimmed,
        {
          onToken: (t) => appendStreamToken(t),
          onChoices: (c) => setChoices(c),
          onStateUpdate: (st) => replaceLatestState(normalizeNarrativeState(st)),
          onError: (msg) => {
            toast.error(msg);
            setParseError(msg);
          },
          onDone: () => {
            endAssistantStream();
            void qc.invalidateQueries({ queryKey: ["sessionMessages", sessionId] });
            void qc.invalidateQueries({ queryKey: ["sessionState", sessionId] });
            void qc.invalidateQueries({ queryKey: ["session", sessionId] });
          },
        },
        { signal: abortRef.current?.signal }
      );
    },
    [
      sessionId,
      streaming,
      archived,
      addUserMessage,
      beginAssistantStream,
      appendStreamToken,
      endAssistantStream,
      setChoices,
      replaceLatestState,
      setParseError,
      qc,
    ]
  );

  const openFeedback = useCallback((messageId: number) => {
    setFeedbackMessageId(messageId);
    setFeedbackOpen(true);
  }, []);

  const handleFeedbackSubmit = useCallback(
    async (payload: { message_id: number; feedback_type: string; content?: string }) => {
      if (!Number.isFinite(sessionId)) return;
      try {
        await postFeedback(sessionId, payload);
        toast.success("反馈已提交");
      } catch (e) {
        toastApiError(e, "提交反馈失败");
        throw e;
      }
    },
    [sessionId]
  );

  if (!Number.isFinite(sessionId)) {
    return (
      <div className="p-8 text-danger">
        无效的会话 ID。
        <Link to="/stories" className="ml-2 text-accent-primary underline">
          返回故事库
        </Link>
      </div>
    );
  }

  const displayTitle = storyTitle || story?.title || "加载中…";
  const mode = session?.mode ?? "strict";
  const inputLocked = streaming || archived;

  const streamingAssistantCharCount = useMemo(() => {
    const a = messages.find((m) => m.role === "assistant" && m.streaming);
    return a ? (a.content ?? "").length : 0;
  }, [messages]);

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] min-w-[1024px] max-w-[1200px] flex-col overflow-hidden px-8 py-6">
      <header className="mb-4 flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <Link
            to="/stories"
            className="inline-flex shrink-0 items-center font-ui text-sm text-text-secondary transition-colors hover:text-accent-primary"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回故事库
          </Link>
          <h1 className="truncate font-story text-xl font-bold text-text-primary">{displayTitle}</h1>
          {session && <ModeBadge mode={mode} />}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/history"
            className="rounded-lg px-3 py-1.5 font-ui text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
          >
            冒险历史
          </Link>
          {sessionActive && (
            <Button size="sm" variant="secondary" onClick={() => setArchiveDialogOpen(true)}>
              结束冒险
            </Button>
          )}
        </div>
      </header>

      {(sessionLoading || (messagesData === undefined && !messagesError)) && (
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden py-24">
          <Loader2 className="h-10 w-10 animate-spin text-accent-primary" />
        </div>
      )}

      {session && messagesData !== undefined && (
        <div className="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-xl border border-border bg-bg-secondary/50 shadow-md">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            {archived && (
              <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-warning/30 bg-warning/10 px-4 py-2 font-ui text-sm text-text-primary">
                <span>会话已归档，无法发送新消息。</span>
                <Button
                  size="sm"
                  variant="primary"
                  isLoading={resumeMut.isPending}
                  onClick={() => resumeMut.mutate()}
                >
                  恢复并继续
                </Button>
                <Link
                  to={`/history/${sessionId}`}
                  className="text-sm text-accent-primary underline hover:brightness-110"
                >
                  查看回看
                </Link>
              </div>
            )}
            {parseError && (
              <div className="shrink-0 border-b border-border bg-danger/10 px-4 py-2 font-ui text-xs text-danger">
                {parseError}
              </div>
            )}
            <div
              ref={scrollRef}
              className="play-session-messages-scroll min-h-0 flex-1 space-y-4 overflow-y-auto p-4"
            >
              {messages.map((m) => (
                <ChatBubble
                  key={`${m.id}-${m.turn_number}`}
                  role={m.role}
                  content={m.content}
                  streaming={m.streaming}
                  messageId={m.id}
                  metadata={m.role === "assistant" ? m.metadata : undefined}
                  onFeedbackClick={m.role === "assistant" ? openFeedback : undefined}
                />
              ))}
            </div>

            <ChoicePanel
              choices={choices}
              disabled={inputLocked}
              streaming={streaming}
              streamingNarrativeCharCount={streamingAssistantCharCount}
              freeInputMode={freeInputMode}
              onToggleFreeInput={setFreeInputMode}
              onSelectChoice={(text) => void sendUserContent(text)}
            />

            {freeInputMode && (
              <MessageInput
                disabled={archived}
                streaming={streaming}
                onSend={(t) => void sendUserContent(t)}
              />
            )}
          </div>

          <div className="flex h-full min-h-0 shrink-0 self-stretch">
            <StatePanel state={latestState} highlightKeys={stateHighlightKeys} />
          </div>
        </div>
      )}

      <FeedbackDialog
        open={feedbackOpen}
        onOpenChange={setFeedbackOpen}
        messageId={feedbackMessageId}
        onSubmit={handleFeedbackSubmit}
      />

      <Dialog open={archiveDialogOpen} onOpenChange={setArchiveDialogOpen}>
        <DialogContent>
          <DialogTitle>结束冒险</DialogTitle>
          <DialogDescription>
            将会话归档为只读。之后可在冒险历史中恢复并继续。
          </DialogDescription>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setArchiveDialogOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              isLoading={archiveMut.isPending}
              onClick={() => archiveMut.mutate()}
            >
              确认归档
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
