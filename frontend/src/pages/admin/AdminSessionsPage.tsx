import { useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../../components/ui/Dialog";
import { Input } from "../../components/ui/Input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/Table";
import {
  useAdminSessionFeedback,
  useAdminSessionsList,
  useAdminTranscript,
} from "../../hooks/useAdminEvalPromptsSessions";
import { stripMetaSuffixForDisplay } from "../../lib/narrativeDisplay";
import { cn } from "../../lib/utils";
import type { AdminSessionListItem } from "../../types/adminSession";

const PAGE = 30;

function formatDt(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function AdminSessionsPage() {
  const [userId, setUserId] = useState("");
  const [storyId, setStoryId] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);

  const listParams = useMemo(() => {
    const p: {
      user_id?: number;
      story_id?: number;
      status?: string;
      limit: number;
      offset: number;
    } = { limit: PAGE, offset };
    if (userId.trim()) {
      const n = parseInt(userId, 10);
      if (!Number.isNaN(n)) p.user_id = n;
    }
    if (storyId.trim()) {
      const n = parseInt(storyId, 10);
      if (!Number.isNaN(n)) p.story_id = n;
    }
    if (status.trim()) p.status = status.trim();
    return p;
  }, [userId, storyId, status, offset]);

  const { data, isLoading } = useAdminSessionsList(listParams);
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;

  const [transcriptSession, setTranscriptSession] = useState<AdminSessionListItem | null>(null);
  const [feedbackSession, setFeedbackSession] = useState<AdminSessionListItem | null>(null);

  return (
    <div className="min-w-[1024px] p-8">
      <header className="mb-8">
        <h1 className="font-story text-2xl font-bold text-text-primary">会话查看</h1>
        <p className="mt-1 text-sm text-text-secondary">全站会话列表、完整 transcript 与用户反馈（管理员）</p>
      </header>

      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-xs text-text-secondary">用户 ID</label>
          <Input value={userId} onChange={(e) => setUserId(e.target.value)} className="w-28" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-secondary">作品 ID</label>
          <Input value={storyId} onChange={(e) => setStoryId(e.target.value)} className="w-28" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-secondary">状态</label>
          <Input
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-28"
            placeholder="active…"
          />
        </div>
        <Button variant="secondary" size="sm" onClick={() => setOffset(0)}>
          应用筛选
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={offset <= 0}
          onClick={() => setOffset((o) => Math.max(0, o - PAGE))}
        >
          上一页
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={offset + PAGE >= total}
          onClick={() => setOffset((o) => o + PAGE)}
        >
          下一页
        </Button>
        <span className="text-xs text-text-secondary">
          {total ? `${offset + 1}–${Math.min(offset + PAGE, total)} / ${total}` : ""}
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>用户</TableHead>
              <TableHead>作品</TableHead>
              <TableHead>模式</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>轮数</TableHead>
              <TableHead>更新</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-text-secondary">
                  加载中…
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-text-secondary">
                  无数据
                </TableCell>
              </TableRow>
            ) : (
              rows.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-mono text-xs">{s.id}</TableCell>
                  <TableCell className="text-xs">
                    {s.username || "—"} <span className="text-text-secondary">({s.user_id})</span>
                  </TableCell>
                  <TableCell className="max-w-[180px] truncate text-xs" title={s.story_title}>
                    {s.story_title || s.story_id}
                  </TableCell>
                  <TableCell className="text-xs">{s.mode}</TableCell>
                  <TableCell className="text-xs">{s.status}</TableCell>
                  <TableCell className="text-xs">{s.turn_count}</TableCell>
                  <TableCell className="text-xs">{formatDt(s.updated_at)}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => setTranscriptSession(s)}>
                      对话
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setFeedbackSession(s)}>
                      反馈
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <TranscriptDialog session={transcriptSession} onClose={() => setTranscriptSession(null)} />
      <FeedbackDialog session={feedbackSession} onClose={() => setFeedbackSession(null)} />
    </div>
  );
}

function TranscriptDialog({
  session,
  onClose,
}: {
  session: AdminSessionListItem | null;
  onClose: () => void;
}) {
  const sid = session?.id ?? null;
  const { data, isLoading } = useAdminTranscript(sid);

  return (
    <Dialog open={sid != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogTitle>会话对话 · #{sid}</DialogTitle>
        <DialogDescription>
          {session ? `${session.story_title} · ${session.mode} · ${session.status}` : ""}
        </DialogDescription>
        {isLoading && <p className="text-sm text-text-secondary">加载中…</p>}
        {data && (
          <div className="mt-4 space-y-3">
            {data.messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "rounded-lg border px-3 py-2 text-sm",
                  m.role === "assistant"
                    ? "border-accent-primary/30 bg-bg-secondary/80"
                    : "border-border bg-bg-hover/40"
                )}
              >
                <div className="mb-1 text-xs font-medium text-text-secondary">
                  {m.role === "assistant" ? "GM" : "玩家"} · 回合 {m.turn_number} · #{m.id}
                </div>
                <p className="whitespace-pre-wrap text-text-primary">
                  {m.role === "assistant"
                    ? stripMetaSuffixForDisplay(m.content, { streaming: false })
                    : m.content}
                </p>
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-text-secondary">metadata JSON</summary>
                  <pre className="mt-1 max-h-32 overflow-auto rounded bg-bg-primary p-2 font-mono text-[10px]">
                    {JSON.stringify(m.metadata ?? {}, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function FeedbackDialog({
  session,
  onClose,
}: {
  session: AdminSessionListItem | null;
  onClose: () => void;
}) {
  const sid = session?.id ?? null;
  const { data, isLoading } = useAdminSessionFeedback(sid);
  const items = data?.items ?? [];

  return (
    <Dialog open={sid != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogTitle>用户反馈 · 会话 #{sid}</DialogTitle>
        {isLoading && <p className="text-sm text-text-secondary">加载中…</p>}
        {!isLoading && items.length === 0 && (
          <p className="text-sm text-text-secondary">暂无反馈</p>
        )}
        <ul className="mt-2 max-h-80 space-y-2 overflow-y-auto text-sm">
          {items.map((f) => (
            <li key={f.id} className="rounded-lg border border-border bg-bg-secondary/50 p-3">
              <p className="text-xs text-text-secondary">
                msg #{f.message_id} · {f.feedback_type} · {f.reviewed ? "已审" : "未审"}
              </p>
              <p className="mt-1 text-text-primary">{f.content || "—"}</p>
              <p className="mt-1 text-[10px] text-text-secondary">{formatDt(f.created_at)}</p>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
