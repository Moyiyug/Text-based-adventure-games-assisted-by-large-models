import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  deleteSession,
  listMySessions,
  resumeSession,
} from "../api/sessionApi";
import { getStory } from "../api/storyApi";
import type { SessionListItem } from "../types/session";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { ModeBadge } from "../components/play/ModeBadge";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/Tabs";
import { cn } from "../lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../components/ui/Dialog";
import { toast, toastApiError } from "../lib/toast";

type FilterKey = "all" | "active" | "archived";

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function truncate(s: string, max: number): string {
  const t = s.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export default function SessionHistoryPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [deleteTarget, setDeleteTarget] = useState<SessionListItem | null>(null);
  const [resumingId, setResumingId] = useState<number | null>(null);

  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ["mySessions"],
    queryFn: listMySessions,
  });

  useEffect(() => {
    if (error) toastApiError(error, "加载会话列表失败");
  }, [error]);

  const storyIds = useMemo(
    () => [...new Set((sessions ?? []).map((s) => s.story_id))],
    [sessions]
  );

  const storyQueries = useQueries({
    queries: storyIds.map((id) => ({
      queryKey: ["story", id] as const,
      queryFn: () => getStory(id),
      enabled: Number.isFinite(id) && id > 0,
    })),
  });

  const titleByStoryId = useMemo(() => {
    const m = new Map<number, string>();
    storyIds.forEach((id, i) => {
      const q = storyQueries[i];
      if (q?.data?.title) m.set(id, q.data.title);
    });
    return m;
  }, [storyIds, storyQueries]);

  const filtered = useMemo(() => {
    if (!sessions) return [];
    if (filter === "all") return sessions;
    return sessions.filter((s) => s.status === filter);
  }, [sessions, filter]);

  const deleteMut = useMutation({
    mutationFn: deleteSession,
    onSuccess: async () => {
      toast.success("会话已删除");
      setDeleteTarget(null);
      await qc.invalidateQueries({ queryKey: ["mySessions"] });
    },
    onError: (e) => toastApiError(e, "删除失败"),
  });

  const handleContinue = async (s: SessionListItem) => {
    try {
      if (s.narrative_status === "completed") {
        navigate(`/history/${s.id}`);
        return;
      }
      if (s.status === "archived") {
        setResumingId(s.id);
        await resumeSession(s.id);
        await qc.invalidateQueries({ queryKey: ["session", s.id] });
      }
      navigate(`/sessions/${s.id}`);
    } catch (e) {
      toastApiError(e, "恢复会话失败");
    } finally {
      setResumingId(null);
    }
  };

  return (
    <div className="mx-auto min-h-[calc(100vh-3.5rem)] min-w-[1024px] max-w-5xl px-6 py-8">
      <header className="mb-6">
        <h1 className="font-story text-2xl font-bold text-text-primary">冒险历史</h1>
        <p className="mt-1 text-sm text-text-secondary">
          继续未完成的会话，或查看只读回看
        </p>
      </header>

      <Tabs
        value={filter}
        onValueChange={(v) => setFilter(v as FilterKey)}
        className="w-full"
      >
        <TabsList>
          <TabsTrigger value="all">全部</TabsTrigger>
          <TabsTrigger value="active">进行中</TabsTrigger>
          <TabsTrigger value="archived">已归档</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="mt-4">
        {isLoading && (
          <div className="flex justify-center py-20 text-text-secondary">
            <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
          </div>
        )}

        {!isLoading && filtered.length === 0 && (
          <p className="rounded-xl border border-border bg-bg-secondary p-8 text-center text-text-secondary">
            暂无会话
          </p>
        )}

        {!isLoading && filtered.length > 0 && (
          <ul className="space-y-3">
            {filtered.map((s) => {
              const title = titleByStoryId.get(s.story_id) ?? `作品 #${s.story_id}`;
              const active = s.status === "active";
              const arcDone = s.narrative_status === "completed";
              return (
                <li
                  key={s.id}
                  className="rounded-xl border border-border bg-bg-secondary/50 p-4 shadow-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate font-story text-lg font-semibold text-text-primary">
                          {title}
                        </h2>
                        <ModeBadge mode={s.mode} />
                        <Badge variant={active ? "success" : "muted"}>
                          {arcDone ? "已完成" : active ? "进行中" : "已归档"}
                        </Badge>
                      </div>
                      <p className="text-sm text-text-secondary">
                        介入意图：{truncate(s.opening_goal, 120)}
                      </p>
                        <p className="font-ui text-xs text-text-secondary">
                          轮数 {s.turn_count} · 创建 {formatWhen(s.created_at)}
                          {s.updated_at &&
                          s.updated_at !== s.created_at &&
                          ` · 更新 ${formatWhen(s.updated_at)}`}
                        </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {arcDone ? (
                        <Link
                          to={`/history/${s.id}`}
                          className={cn(
                            "inline-flex h-9 items-center justify-center rounded-lg bg-accent-primary px-4 text-sm font-medium text-white transition-colors hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20"
                          )}
                        >
                          查看回看
                        </Link>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant={active ? "primary" : "secondary"}
                            isLoading={resumingId === s.id}
                            onClick={() => void handleContinue(s)}
                          >
                            {active ? "继续游玩" : "恢复并继续"}
                          </Button>
                          <Link
                            to={`/history/${s.id}`}
                            className={cn(
                              "inline-flex h-9 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium text-text-primary transition-colors hover:bg-bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20"
                            )}
                          >
                            查看回看
                          </Link>
                        </>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-danger hover:text-danger"
                        onClick={() => setDeleteTarget(s)}
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogTitle>删除会话</DialogTitle>
          <DialogDescription>
            将永久删除该会话及全部消息与状态，不可恢复。确定吗？
          </DialogDescription>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button
              variant="danger"
              isLoading={deleteMut.isPending}
              onClick={() => {
                if (deleteTarget) deleteMut.mutate(deleteTarget.id);
              }}
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
