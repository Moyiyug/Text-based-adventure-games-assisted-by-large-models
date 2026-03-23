import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../ui/Dialog";
import { Button } from "../ui/Button";
import { Textarea } from "../ui/Textarea";

const FEEDBACK_TYPES = [
  { value: "like", label: "喜欢" },
  { value: "dislike", label: "不喜欢" },
  { value: "issue", label: "问题反馈" },
  { value: "other", label: "其他" },
] as const;

interface FeedbackDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  messageId: number | null;
  onSubmit: (payload: { message_id: number; feedback_type: string; content?: string }) => Promise<void>;
}

export function FeedbackDialog({
  open,
  onOpenChange,
  messageId,
  onSubmit,
}: FeedbackDialogProps) {
  const [type, setType] = useState<string>("like");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) {
      setType("like");
      setContent("");
      setLoading(false);
    }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (messageId == null || messageId <= 0) return;
    setLoading(true);
    try {
      await onSubmit({
        message_id: messageId,
        feedback_type: type,
        content: content.trim() || undefined,
      });
      onOpenChange(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" onPointerDownOutside={(ev) => ev.preventDefault()}>
        <form onSubmit={handleSubmit}>
          <DialogTitle>叙事反馈</DialogTitle>
          <DialogDescription>选择类型并可选填写说明（将关联到当前 GM 消息）。</DialogDescription>

          <div className="mt-4 space-y-3">
            <fieldset>
              <legend className="text-sm font-medium text-text-primary">反馈类型</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {FEEDBACK_TYPES.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex cursor-pointer items-center gap-2 rounded-lg border border-border px-3 py-2 font-ui text-sm text-text-primary hover:bg-bg-hover"
                  >
                    <input
                      type="radio"
                      name="fb-type"
                      value={opt.value}
                      checked={type === opt.value}
                      onChange={() => setType(opt.value)}
                      className="h-4 w-4 accent-accent-primary"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <label htmlFor="fb-content" className="text-sm font-medium text-text-primary">
                补充说明（可选）
              </label>
              <Textarea
                id="fb-content"
                className="mt-2"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                disabled={loading}
                maxLength={2000}
                placeholder="可描述具体问题或建议…"
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" isLoading={loading} disabled={messageId == null || messageId <= 0}>
              提交
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
