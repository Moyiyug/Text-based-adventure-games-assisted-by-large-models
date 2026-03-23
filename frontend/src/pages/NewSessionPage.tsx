import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { getStory } from "../api/storyApi";
import { createSession } from "../api/sessionApi";
import type { SessionMode } from "../types/session";
import { Button } from "../components/ui/Button";
import { Textarea } from "../components/ui/Textarea";
import { toast, toastApiError } from "../lib/toast";

export default function NewSessionPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const sid = storyId ? Number(storyId) : NaN;

  const [mode, setMode] = useState<SessionMode>("strict");
  const [openingGoal, setOpeningGoal] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { data: story, isLoading, error } = useQuery({
    queryKey: ["story", sid],
    queryFn: () => getStory(sid),
    enabled: Number.isFinite(sid),
  });

  useEffect(() => {
    if (error) toastApiError(error, "加载作品失败");
  }, [error]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const goal = openingGoal.trim();
    if (!goal) {
      toast.error("请填写冒险目标");
      return;
    }
    if (!Number.isFinite(sid)) return;
    setSubmitting(true);
    try {
      const session = await createSession({
        story_id: sid,
        mode,
        opening_goal: goal,
      });
      toast.success("会话已创建");
      navigate(`/sessions/${session.id}`, { replace: true });
    } catch (err) {
      toastApiError(err, "创建会话失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (!Number.isFinite(sid)) {
    return (
      <div className="p-8 text-danger">
        无效的作品 ID。
        <Link to="/stories" className="ml-2 text-accent-primary underline">
          返回故事库
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-[calc(100vh-3.5rem)] max-w-xl px-6 py-8">
      <Link
        to="/stories"
        className="mb-6 inline-flex items-center text-sm text-text-secondary hover:text-accent-primary transition-colors"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        返回故事库
      </Link>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
        </div>
      )}

      {story && (
        <>
          <h1 className="font-story text-2xl font-bold text-text-primary">{story.title}</h1>
          <p className="mt-2 text-sm text-text-secondary line-clamp-3">
            {story.description || "暂无简介"}
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-6">
            <fieldset>
              <legend className="text-sm font-medium text-text-primary">叙事模式</legend>
              <div className="mt-3 flex gap-6">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-text-primary">
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === "strict"}
                    onChange={() => setMode("strict")}
                    className="h-4 w-4 accent-accent-primary"
                  />
                  严谨
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-text-primary">
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === "creative"}
                    onChange={() => setMode("creative")}
                    className="h-4 w-4 accent-accent-primary"
                  />
                  创作
                </label>
              </div>
            </fieldset>

            <div>
              <label htmlFor="opening-goal" className="text-sm font-medium text-text-primary">
                冒险目标
              </label>
              <Textarea
                id="opening-goal"
                className="mt-2"
                placeholder="描述你希望在本作中达成的体验或目标…"
                value={openingGoal}
                onChange={(e) => setOpeningGoal(e.target.value)}
                disabled={submitting}
                maxLength={8000}
              />
            </div>

            <Button type="submit" size="lg" className="w-full" isLoading={submitting}>
              开始冒险
            </Button>
          </form>
        </>
      )}
    </div>
  );
}
