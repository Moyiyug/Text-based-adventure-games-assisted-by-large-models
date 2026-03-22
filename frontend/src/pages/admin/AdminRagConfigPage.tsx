import { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../../components/ui/Dialog";
import { Input } from "../../components/ui/Input";
import {
  useActivateRagConfig,
  useRagConfigs,
  useUpdateRagConfig,
} from "../../hooks/useAdminApi";
import { toast, toastApiError } from "../../lib/toast";
import { cn } from "../../lib/utils";
import type { RagConfigRow } from "../../api/adminRagConfigs";

const VARIANT_LABEL: Record<string, string> = {
  naive_hybrid: "朴素混合 RAG",
  parent_child: "父子块分层",
  structured: "结构化辅助",
};

function variantTitle(row: RagConfigRow): string {
  return VARIANT_LABEL[row.variant_type] ?? row.variant_type;
}

const textareaClass =
  "min-h-[200px] w-full rounded-lg border border-border bg-bg-primary px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20";

export default function AdminRagConfigPage() {
  const { data, isLoading, isError, refetch } = useRagConfigs();
  const updateMut = useUpdateRagConfig();
  const activateMut = useActivateRagConfig();

  const [nameDrafts, setNameDrafts] = useState<Record<number, string>>({});
  const [jsonDrafts, setJsonDrafts] = useState<Record<number, string>>({});
  const [activateId, setActivateId] = useState<number | null>(null);

  useEffect(() => {
    if (!data) return;
    setNameDrafts((prev) => {
      const next = { ...prev };
      for (const r of data) {
        if (next[r.id] === undefined) next[r.id] = r.name;
      }
      return next;
    });
    setJsonDrafts((prev) => {
      const next = { ...prev };
      for (const r of data) {
        if (next[r.id] === undefined) next[r.id] = JSON.stringify(r.config, null, 2);
      }
      return next;
    });
  }, [data]);

  const rows = useMemo(() => data ?? [], [data]);

  const pendingActivate = useMemo(
    () => (activateId != null ? rows.find((r) => r.id === activateId) : null),
    [activateId, rows]
  );

  const handleSave = async (id: number) => {
    const raw = jsonDrafts[id];
    const nameVal = nameDrafts[id]?.trim();
    if (raw === undefined) {
      toast.error("参数内容缺失");
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw) as Record<string, unknown>;
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        toast.error("配置必须是 JSON 对象");
        return;
      }
    } catch {
      toast.error("JSON 格式无效");
      return;
    }
    try {
      const row = await updateMut.mutateAsync({
        id,
        body: {
          name: nameVal || undefined,
          config: parsed,
        },
      });
      setJsonDrafts((s) => ({ ...s, [id]: JSON.stringify(row.config, null, 2) }));
      setNameDrafts((s) => ({ ...s, [id]: row.name }));
      toast.success("已保存");
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  const confirmActivate = async () => {
    if (activateId == null) return;
    try {
      await activateMut.mutateAsync(activateId);
      toast.success("已切换当前方案");
      setActivateId(null);
    } catch (e) {
      toastApiError(e, "激活失败");
    }
  };

  return (
    <div className="p-6 text-text-primary">
      <h1 className="font-story text-xl font-bold">RAG 方案配置</h1>
      <p className="mt-1 max-w-2xl text-sm text-text-secondary">
        切换全局激活的检索方案（A/B/C），并编辑各方案的 JSON 参数。激活后新会话将使用该方案（具体绑定在 Phase 4
        会话 API 中实现）。
      </p>

      {isLoading && <p className="mt-8 text-sm text-text-secondary">加载中…</p>}
      {isError && (
        <p className="mt-8 text-sm text-danger">
          加载失败。
          <button type="button" className="ml-2 underline" onClick={() => refetch()}>
            重试
          </button>
        </p>
      )}

      {data && (
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((row) => (
            <div
              key={row.id}
              className={cn(
                "flex flex-col rounded-xl border bg-bg-secondary p-4 shadow-sm transition-shadow",
                row.is_active
                  ? "border-2 border-accent-primary ring-2 ring-accent-primary/25"
                  : "border-border"
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-accent-primary">
                    {variantTitle(row)}
                  </p>
                  <p className="mt-0.5 text-xs text-text-secondary">id: {row.id}</p>
                </div>
                {row.is_active && (
                  <span className="rounded-full bg-accent-primary/15 px-2 py-0.5 text-xs font-medium text-accent-primary">
                    当前激活
                  </span>
                )}
              </div>

              <label className="mt-3 block text-xs text-text-secondary">
                显示名称
                <Input
                  className="mt-1"
                  value={nameDrafts[row.id] ?? row.name}
                  onChange={(e) =>
                    setNameDrafts((s) => ({ ...s, [row.id]: e.target.value }))
                  }
                  maxLength={50}
                />
              </label>

              <label className="mt-3 block flex-1 text-xs text-text-secondary">
                参数（JSON）
                <textarea
                  className={cn(textareaClass, "mt-1 flex-1")}
                  spellCheck={false}
                  value={jsonDrafts[row.id] ?? JSON.stringify(row.config, null, 2)}
                  onChange={(e) =>
                    setJsonDrafts((s) => ({ ...s, [row.id]: e.target.value }))
                  }
                />
              </label>

              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  isLoading={updateMut.isPending}
                  onClick={() => handleSave(row.id)}
                >
                  保存
                </Button>
                {!row.is_active && (
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => setActivateId(row.id)}
                  >
                    设为当前方案
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={activateId !== null} onOpenChange={(o) => !o && setActivateId(null)}>
        <DialogContent>
          <DialogTitle>确认切换方案？</DialogTitle>
          <DialogDescription>
            将全局激活方案改为「{pendingActivate ? variantTitle(pendingActivate) : "—"}」
            （{pendingActivate?.name ?? "—"}）。其他方案将变为未激活状态。
          </DialogDescription>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setActivateId(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              isLoading={activateMut.isPending}
              onClick={() => void confirmActivate()}
            >
              确认激活
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
