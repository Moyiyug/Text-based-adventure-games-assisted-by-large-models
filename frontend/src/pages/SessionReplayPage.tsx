import axios from "axios";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import {
  getSession,
  getSessionMessages,
  getSessionState,
  resumeSession,
} from "../api/sessionApi";
import { getStory } from "../api/storyApi";
import type { NarrativeState } from "../types/session";
import { ChatBubble } from "../components/play/ChatBubble";
import { StatePanel } from "../components/play/StatePanel";
import { ModeBadge } from "../components/play/ModeBadge";
import { Button } from "../components/ui/Button";
import { toastApiError } from "../lib/toast";
import { cn } from "../lib/utils";

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

export default function SessionReplayPage() {
  const { sessionId: sid } = useParams<{ sessionId: string }>();
  const sessionId = sid ? Number(sid) : NaN;
  const navigate = useNavigate();
  const qc = useQueryClient();

  const {
    data: session,
    isLoading: sessionLoading,
    error: sessionError,
  } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId),
    enabled: Number.isFinite(sessionId),
  });

  const { data: messages, isLoading: msgLoading, error: msgError } = useQuery({
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

  useEffect(() => {
    if (sessionError) toastApiError(sessionError, "加载会话失败");
  }, [sessionError]);

  useEffect(() => {
    if (msgError) toastApiError(msgError, "加载消息失败");
  }, [msgError]);

  const resumeMut = useMutation({
    mutationFn: () => resumeSession(sessionId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["session", sessionId] });
      await qc.invalidateQueries({ queryKey: ["mySessions"] });
      navigate(`/sessions/${sessionId}`);
    },
    onError: (e) => toastApiError(e, "恢复会话失败"),
  });

  const rawLatest = stateSnap?.state ?? session?.latest_state?.state;
  const panelState: NarrativeState | null = rawLatest
    ? normalizeNarrativeState(rawLatest as unknown as Record<string, unknown>)
    : null;

  const archived = session?.status === "archived";
  const active = session?.status === "active";
  const storyLineComplete = session?.narrative_status === "completed";

  if (!Number.isFinite(sessionId)) {
    return (
      <div className="p-8 text-danger">
        无效的会话 ID。
        <Link to="/history" className="ml-2 text-accent-primary underline">
          返回历史
        </Link>
      </div>
    );
  }

  const loading = sessionLoading || msgLoading;
  const displayTitle = story?.title ?? "加载中…";

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] min-w-[1024px] max-w-[1200px] flex-col px-8 py-6">
      <header className="mb-4 flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-4">
          <Link
            to="/history"
            className="inline-flex shrink-0 items-center font-ui text-sm text-text-secondary transition-colors hover:text-accent-primary"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回历史
          </Link>
          <h1 className="truncate font-story text-xl font-bold text-text-primary">
            {displayTitle} · 回看
          </h1>
          {session && <ModeBadge mode={session.mode} />}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {storyLineComplete && (
            <span className="font-ui text-xs text-text-secondary">故事线已完成 · 仅回看</span>
          )}
          {active && !storyLineComplete && (
            <Button size="sm" onClick={() => navigate(`/sessions/${sessionId}`)}>
              继续游玩
            </Button>
          )}
          {archived && !storyLineComplete && (
            <Button
              size="sm"
              variant="primary"
              isLoading={resumeMut.isPending}
              onClick={() => resumeMut.mutate()}
            >
              恢复并继续
            </Button>
          )}
        </div>
      </header>

      <p className="mb-4 text-xs text-text-secondary">
        只读回看。完整逐轮状态历史待后端 API 时可在本页扩展；当前展示会话最新状态快照。
      </p>

      {loading && (
        <div className="flex flex-1 items-center justify-center py-24">
          <Loader2 className="h-10 w-10 animate-spin text-accent-primary" />
        </div>
      )}

      {!loading && session && messages && (
        <div className="flex min-h-0 flex-1 gap-0 overflow-hidden rounded-xl border border-border bg-bg-secondary/50 shadow-md">
          <div
            className={cn(
              "play-session-messages-scroll min-h-0 min-w-0 flex-1 space-y-4 overflow-y-auto p-4",
              "max-h-[calc(100vh-14rem)]"
            )}
          >
            {messages.map((m) => (
              <ChatBubble
                key={`${m.id}-${m.turn_number}`}
                role={m.role}
                content={m.content}
                streaming={false}
                messageId={m.id}
                metadata={m.role === "assistant" ? m.metadata : undefined}
              />
            ))}
          </div>
          <div className="flex max-h-[calc(100vh-14rem)] min-h-0 shrink-0 self-stretch border-l border-border">
            <StatePanel
              state={panelState}
              highlightKeys={[]}
              narrativeStatus={session.narrative_status}
              narrativePlan={session.narrative_plan}
            />
          </div>
        </div>
      )}

      {!loading && session && messages && (
        <div className="mt-4 flex flex-wrap justify-center gap-2 border-t border-border pt-4">
          {active && !storyLineComplete && (
            <Button onClick={() => navigate(`/sessions/${sessionId}`)}>继续游玩</Button>
          )}
          {archived && !storyLineComplete && (
            <Button
              variant="primary"
              isLoading={resumeMut.isPending}
              onClick={() => resumeMut.mutate()}
            >
              恢复并继续
            </Button>
          )}
          {storyLineComplete && (
            <span className="self-center font-ui text-sm text-text-secondary">
              本会话故事线已结束，不提供继续游玩或恢复推进。
            </span>
          )}
        </div>
      )}
    </div>
  );
}
