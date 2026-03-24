import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Plus } from "lucide-react";
import { Button } from "../../components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../../components/ui/Dialog";
import { Input } from "../../components/ui/Input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/Tabs";
import {
  useCreatePromptTemplate,
  usePromptsGrouped,
  useUpdatePromptTemplate,
} from "../../hooks/useAdminEvalPromptsSessions";
import { toast, toastApiError } from "../../lib/toast";
import { cn } from "../../lib/utils";
import type { PromptTemplateAdminOut } from "../../types/promptTemplate";

const textareaClass =
  "min-h-[220px] w-full rounded-lg border border-border bg-bg-primary px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20";

export default function AdminPromptsPage() {
  const { data, isLoading, isError } = usePromptsGrouped();
  const updateMut = useUpdatePromptTemplate();
  const createMut = useCreatePromptTemplate();

  const [openLayers, setOpenLayers] = useState<Record<string, boolean>>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newLayer, setNewLayer] = useState("gm");
  const [newMode, setNewMode] = useState("all");
  const [newText, setNewText] = useState("");

  const layers = data?.layers ?? [];

  useEffect(() => {
    setOpenLayers((prev) => {
      const next = { ...prev };
      for (const L of layers) {
        if (next[L.layer] === undefined) next[L.layer] = true;
      }
      return next;
    });
  }, [layers]);

  const toggleLayer = (layer: string) => {
    setOpenLayers((s) => ({ ...s, [layer]: !s[layer] }));
  };

  const handleCreate = async () => {
    if (!newName.trim() || !newText.trim()) {
      toast.error("请填写名称与模板正文");
      return;
    }
    try {
      await createMut.mutateAsync({
        name: newName.trim(),
        layer: newLayer.trim(),
        template_text: newText,
        applicable_mode: newMode.trim() || "all",
        is_active: true,
      });
      toast.success("已新建模板");
      setCreateOpen(false);
      setNewName("");
      setNewText("");
    } catch (e) {
      toastApiError(e, "创建失败");
    }
  };

  return (
    <div className="min-w-[1024px] p-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-story text-2xl font-bold text-text-primary">提示词编辑</h1>
          <p className="mt-1 text-sm text-text-secondary">
            按 layer × mode 分组；展开后编辑正文并保存（可选递增版本号）
          </p>
        </div>
        <Button variant="secondary" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1 inline h-4 w-4" />
          新建模板
        </Button>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogTitle>新建提示词模板</DialogTitle>
          <DialogDescription>layer 须与管线一致（如 system / retrieval / gm / style）</DialogDescription>
          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">名称</label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">layer</label>
              <Input value={newLayer} onChange={(e) => setNewLayer(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">applicable_mode</label>
              <Input value={newMode} onChange={(e) => setNewMode(e.target.value)} placeholder="all / strict / creative" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">template_text</label>
              <textarea
                className={textareaClass}
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleCreate()} isLoading={createMut.isPending}>
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isLoading && <p className="text-text-secondary">加载中…</p>}
      {isError && <p className="text-danger">加载失败</p>}

      <div className="space-y-3">
        {layers.map((layerGroup) => (
          <LayerSection
            key={layerGroup.layer}
            layer={layerGroup.layer}
            open={openLayers[layerGroup.layer] !== false}
            onToggle={() => toggleLayer(layerGroup.layer)}
            modes={layerGroup.by_mode}
            updateMut={updateMut}
          />
        ))}
      </div>
    </div>
  );
}

function LayerSection({
  layer,
  open,
  onToggle,
  modes,
  updateMut,
}: {
  layer: string;
  open: boolean;
  onToggle: () => void;
  modes: Record<string, PromptTemplateAdminOut[]>;
  updateMut: ReturnType<typeof useUpdatePromptTemplate>;
}) {
  const modeKeys = useMemo(() => Object.keys(modes).sort(), [modes]);
  const defaultTab = modeKeys[0] ?? "all";

  return (
    <div className="rounded-xl border border-border bg-bg-secondary/50 shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-4 py-3 text-left font-ui text-sm font-semibold text-text-primary hover:bg-bg-hover/50"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        Layer: <span className="font-mono text-accent-primary">{layer}</span>
      </button>
      {open && (
        <div className="border-t border-border px-4 pb-4 pt-2">
          {modeKeys.length === 0 ? (
            <p className="text-sm text-text-secondary">无模板</p>
          ) : (
            <Tabs defaultValue={defaultTab}>
              <TabsList className="flex-wrap">
                {modeKeys.map((m) => (
                  <TabsTrigger key={m} value={m}>
                    {m}
                  </TabsTrigger>
                ))}
              </TabsList>
              {modeKeys.map((m) => (
                <TabsContent key={m} value={m} className="space-y-4">
                  {(modes[m] ?? []).map((t) => (
                    <PromptEditorCard key={t.id} template={t} updateMut={updateMut} />
                  ))}
                </TabsContent>
              ))}
            </Tabs>
          )}
        </div>
      )}
    </div>
  );
}

function PromptEditorCard({
  template,
  updateMut,
}: {
  template: PromptTemplateAdminOut;
  updateMut: ReturnType<typeof useUpdatePromptTemplate>;
}) {
  const [text, setText] = useState(template.template_text);
  const [bump, setBump] = useState(false);

  useEffect(() => {
    setText(template.template_text);
  }, [template.id, template.version, template.template_text]);

  const save = async () => {
    try {
      await updateMut.mutateAsync({
        id: template.id,
        body: { template_text: text, bump_version: bump },
      });
      toast.success("已保存");
      setBump(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  return (
    <div className={cn("rounded-lg border border-border bg-bg-primary p-4")}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        <span className="font-medium text-text-primary">{template.name}</span>
        <span>· v{template.version}</span>
        <span>· {template.is_active ? "启用" : "停用"}</span>
        <span className="font-mono">id={template.id}</span>
      </div>
      <textarea className={textareaClass} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-text-primary">
          <input type="checkbox" checked={bump} onChange={(e) => setBump(e.target.checked)} />
          保存并递增版本号
        </label>
        <Button size="sm" onClick={() => void save()} isLoading={updateMut.isPending}>
          保存
        </Button>
      </div>
    </div>
  );
}
