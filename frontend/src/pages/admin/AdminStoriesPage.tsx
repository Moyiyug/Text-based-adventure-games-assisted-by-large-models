import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Upload } from "lucide-react";
import { ActionMenu } from "../../components/ui/ActionMenu";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../../components/ui/Dialog";
import { Input } from "../../components/ui/Input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/Table";
import {
  useAdminStories,
  useDeleteStory,
  useIngestionJobs,
  useIngestionWarnings,
  useRollbackStory,
  useTriggerIngest,
  useUpdateStory,
  useUploadStory,
} from "../../hooks/useAdminApi";
import { toast, toastApiError } from "../../lib/toast";
import { cn } from "../../lib/utils";
import type { AdminStoryListItem, IngestionJob } from "../../api/adminStories";

const UPLOAD_ACCEPT = ".txt,.md,.pdf,.docx,.json";
const UPLOAD_EXT = [".txt", ".md", ".pdf", ".docx", ".json"];

function isAcceptedUploadFile(file: File) {
  const n = file.name.toLowerCase();
  return UPLOAD_EXT.some((ext) => n.endsWith(ext));
}

function statusBadge(status: string) {
  switch (status) {
    case "ready":
      return <Badge variant="success">已就绪</Badge>;
    case "ingesting":
      return <Badge variant="warning">入库中</Badge>;
    case "failed":
      return <Badge variant="danger">失败</Badge>;
    default:
      return <Badge variant="muted">待处理</Badge>;
  }
}

function formatDt(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function AdminStoriesPage() {
  const navigate = useNavigate();
  const { data: stories = [], isLoading } = useAdminStories(false);
  const uploadMut = useUploadStory();
  const updateMut = useUpdateStory();
  const deleteMut = useDeleteStory();
  const ingestMut = useTriggerIngest();
  const rollbackMut = useRollbackStory();

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDesc, setUploadDesc] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDragOver, setUploadDragOver] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  const setFileFromBrowser = (list: FileList | null) => {
    const f = list?.[0];
    if (!f) return;
    if (!isAcceptedUploadFile(f)) {
      toast.error("仅支持 txt / md / pdf / docx / json");
      return;
    }
    setUploadFile(f);
  };

  const [editStory, setEditStory] = useState<AdminStoryListItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<AdminStoryListItem | null>(null);
  const [rollbackTarget, setRollbackTarget] = useState<AdminStoryListItem | null>(null);
  const [rollbackVersion, setRollbackVersion] = useState("");

  const [jobsStory, setJobsStory] = useState<AdminStoryListItem | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  const jobsQuery = useIngestionJobs(jobsStory?.id ?? null, { poll: true });
  const warningsQuery = useIngestionWarnings(jobsStory?.id ?? null, selectedJobId);

  const sortedJobs = useMemo(() => {
    const jobs = jobsQuery.data ?? [];
    return [...jobs].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [jobsQuery.data]);

  const openJobs = (s: AdminStoryListItem) => {
    setJobsStory(s);
    setSelectedJobId(null);
  };

  const handleUpload = async () => {
    if (!uploadTitle.trim() || !uploadFile) {
      toast.error("请填写标题并选择文件");
      return;
    }
    const fd = new FormData();
    fd.append("title", uploadTitle.trim());
    if (uploadDesc.trim()) fd.append("description", uploadDesc.trim());
    fd.append("file", uploadFile);
    try {
      await uploadMut.mutateAsync(fd);
      toast.success("上传成功，可触发入库");
      setUploadOpen(false);
      setUploadTitle("");
      setUploadDesc("");
      setUploadFile(null);
    } catch (e) {
      toastApiError(e, "上传失败");
    }
  };

  const saveEdit = async () => {
    if (!editStory) return;
    try {
      await updateMut.mutateAsync({
        id: editStory.id,
        body: {
          title: editTitle.trim() || undefined,
          description: editDesc.trim() || null,
        },
      });
      toast.success("已保存");
      setEditStory(null);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMut.mutateAsync(deleteTarget.id);
      toast.success("已软删除");
      setDeleteTarget(null);
    } catch (e) {
      toastApiError(e, "删除失败");
    }
  };

  const confirmRollback = async () => {
    if (!rollbackTarget) return;
    const v = rollbackVersion.trim();
    const targetVersionId = v === "" ? null : Number(v);
    if (v !== "" && !Number.isFinite(targetVersionId)) {
      toast.error("版本号无效");
      return;
    }
    try {
      await rollbackMut.mutateAsync({ id: rollbackTarget.id, targetVersionId });
      toast.success("已回滚版本");
      setRollbackTarget(null);
      setRollbackVersion("");
    } catch (e) {
      toastApiError(e, "回滚失败");
    }
  };

  const triggerIngest = async (id: number) => {
    try {
      await ingestMut.mutateAsync(id);
      toast.success("入库任务已提交");
    } catch (e) {
      toastApiError(e, "触发入库失败");
    }
  };

  return (
    <div className="p-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-story text-2xl font-bold text-text-primary">作品与入库</h1>
          <p className="mt-1 text-sm text-text-secondary">上传源文件、触发解析与向量化、查看任务与警告</p>
        </div>
        <Button onClick={() => setUploadOpen(true)}>上传作品</Button>
      </div>

      <Dialog
        open={uploadOpen}
        onOpenChange={(o) => {
          setUploadOpen(o);
          if (!o) setUploadDragOver(false);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogTitle>上传作品</DialogTitle>
          <DialogDescription>支持 txt / md / pdf / docx / json</DialogDescription>
          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">标题</label>
              <Input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} placeholder="作品标题" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-secondary">简介（可选）</label>
              <Input value={uploadDesc} onChange={(e) => setUploadDesc(e.target.value)} placeholder="简介" />
            </div>
            <div>
              <p className="mb-1 text-xs font-medium text-text-secondary">文件</p>
              <div
                role="button"
                tabIndex={0}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-8 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/40",
                  uploadDragOver
                    ? "border-accent-primary bg-accent-primary/10"
                    : "border-border bg-bg-hover/50 hover:bg-bg-hover"
                )}
                onClick={() => uploadInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    uploadInputRef.current?.click();
                  }
                }}
                onDragEnter={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setUploadDragOver(true);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setUploadDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setUploadDragOver(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setUploadDragOver(false);
                  setFileFromBrowser(e.dataTransfer.files);
                }}
              >
                <Upload className="mb-2 h-8 w-8 text-text-secondary" />
                <span className="text-center text-sm text-text-secondary">
                  {uploadFile ? uploadFile.name : "点击选择或拖拽文件到此处"}
                </span>
                <input
                  ref={uploadInputRef}
                  type="file"
                  className="sr-only"
                  accept={UPLOAD_ACCEPT}
                  onChange={(e) => {
                    setFileFromBrowser(e.target.files);
                    e.target.value = "";
                  }}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setUploadOpen(false)}>
              取消
            </Button>
            <Button onClick={handleUpload} isLoading={uploadMut.isPending}>
              上传
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!editStory}
        onOpenChange={(o) => {
          if (!o) setEditStory(null);
        }}
      >
        <DialogContent>
          <DialogTitle>编辑作品信息</DialogTitle>
          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">标题</label>
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">简介</label>
              <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEditStory(null)}>
              取消
            </Button>
            <Button onClick={saveEdit} isLoading={updateMut.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => {
          if (!o) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogTitle>确认软删除？</DialogTitle>
          <DialogDescription>
            作品「{deleteTarget?.title}」将不再在列表与玩家端展示，数据保留以便审计。
          </DialogDescription>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button variant="danger" onClick={confirmDelete} isLoading={deleteMut.isPending}>
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!rollbackTarget}
        onOpenChange={(o) => {
          if (!o) {
            setRollbackTarget(null);
            setRollbackVersion("");
          }
        }}
      >
        <DialogContent>
          <DialogTitle>回滚到备份版本</DialogTitle>
          <DialogDescription>
            留空则使用当前备份版本与生效版本互换；也可填写目标 <code className="font-mono text-xs">story_version_id</code>
            。
          </DialogDescription>
          <div className="mt-4">
            <label className="mb-1 block text-xs text-text-secondary">目标版本 ID（可选）</label>
            <Input
              value={rollbackVersion}
              onChange={(e) => setRollbackVersion(e.target.value)}
              placeholder="留空 = 默认备份版本"
            />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setRollbackTarget(null)}>
              取消
            </Button>
            <Button onClick={confirmRollback} isLoading={rollbackMut.isPending}>
              确认回滚
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!jobsStory}
        onOpenChange={(o) => {
          if (!o) {
            setJobsStory(null);
            setSelectedJobId(null);
          }
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogTitle>入库任务：{jobsStory?.title}</DialogTitle>
          <DialogDescription>进行中任务会自动刷新；选择任务可查看 IngestionWarning 列表</DialogDescription>
          <div className="mt-4 space-y-3">
            {jobsQuery.isLoading ? (
              <p className="text-sm text-text-secondary">加载中…</p>
            ) : sortedJobs.length === 0 ? (
              <p className="text-sm text-text-secondary">暂无任务</p>
            ) : (
              <ul className="space-y-2">
                {sortedJobs.map((j: IngestionJob) => (
                  <li key={j.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedJobId(j.id)}
                      className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        selectedJobId === j.id
                          ? "border-accent-primary bg-bg-hover"
                          : "border-border hover:bg-bg-hover/80"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-xs text-text-secondary">#{j.id}</span>
                        <Badge
                          variant={
                            j.status === "completed"
                              ? "success"
                              : j.status === "failed"
                                ? "danger"
                                : "warning"
                          }
                        >
                          {j.status}
                        </Badge>
                      </div>
                      <div className="mt-1 text-text-secondary">
                        进度 {(j.progress * 100).toFixed(0)}% · {formatDt(j.created_at)}
                      </div>
                      {j.error_message && (
                        <p className="mt-1 text-xs text-danger line-clamp-3">{j.error_message}</p>
                      )}
                      {Array.isArray(j.steps_completed) && j.steps_completed.length > 0 && (
                        <p className="mt-1 text-xs text-text-secondary">
                          步骤：{j.steps_completed.join(" → ")}
                        </p>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {selectedJobId != null && (
              <div className="rounded-lg border border-border bg-bg-hover/40 p-3">
                <p className="mb-2 text-sm font-medium text-text-primary">警告与提示（job #{selectedJobId}）</p>
                {warningsQuery.isLoading ? (
                  <p className="text-xs text-text-secondary">加载警告…</p>
                ) : !warningsQuery.data?.length ? (
                  <p className="text-xs text-text-secondary">本条任务无警告记录</p>
                ) : (
                  <ul className="max-h-48 space-y-2 overflow-y-auto text-xs">
                    {warningsQuery.data.map((w) => (
                      <li key={w.id} className="rounded border border-border/80 bg-bg-secondary p-2">
                        <span className="font-mono text-text-secondary">{w.warning_type}</span>
                        <p className="mt-1 text-text-primary">{w.message}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <p className="text-sm text-text-secondary">加载中…</p>
      ) : stories.length === 0 ? (
        <p className="rounded-xl border border-border bg-bg-secondary p-8 text-center text-sm text-text-secondary shadow-sm">
          暂无作品，点击「上传作品」开始
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>标题</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>版本</TableHead>
              <TableHead>最后入库完成</TableHead>
              <TableHead className="w-24 text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stories.map((s) => (
              <TableRow key={s.id}>
                <TableCell>
                  <div className="font-medium text-text-primary">{s.title}</div>
                  {s.description && (
                    <div className="mt-0.5 line-clamp-1 text-xs text-text-secondary">{s.description}</div>
                  )}
                </TableCell>
                <TableCell>{statusBadge(s.status)}</TableCell>
                <TableCell className="text-text-secondary">{s.version_count}</TableCell>
                <TableCell className="text-text-secondary text-xs">{formatDt(s.last_ingested_at)}</TableCell>
                <TableCell className="text-right">
                  <ActionMenu
                    items={[
                      {
                        label: "编辑信息",
                        onSelect: () => {
                          setEditStory(s);
                          setEditTitle(s.title);
                          setEditDesc(s.description ?? "");
                        },
                      },
                      {
                        label: "触发入库",
                        onSelect: () => triggerIngest(s.id),
                        disabled: s.status === "ingesting",
                      },
                      {
                        label: "入库任务",
                        onSelect: () => openJobs(s),
                      },
                      {
                        label: "元数据编辑",
                        onSelect: () => navigate(`/admin/metadata?story=${s.id}`),
                      },
                      {
                        label: "版本回滚",
                        onSelect: () => setRollbackTarget(s),
                        disabled: s.status === "ingesting",
                      },
                      {
                        label: "软删除",
                        onSelect: () => setDeleteTarget(s),
                        destructive: true,
                      },
                    ]}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <p className="mt-6 text-xs text-text-secondary">
        也可用{" "}
        <Link to="/admin/metadata" className="text-accent-primary underline">
          元数据编辑
        </Link>{" "}
        页维护实体与关系。
      </p>
    </div>
  );
}
