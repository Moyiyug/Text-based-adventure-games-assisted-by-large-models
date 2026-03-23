import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { listStories } from "../api/storyApi";
import { StoryCard } from "../components/story/StoryCard";
import { toastApiError } from "../lib/toast";

export default function StoryLibraryPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["stories", "player"],
    queryFn: listStories,
  });

  useEffect(() => {
    if (error) toastApiError(error, "加载故事列表失败");
  }, [error]);

  return (
    <div className="mx-auto min-h-[calc(100vh-3.5rem)] max-w-6xl px-6 py-8">
      <header className="mb-8">
        <h1 className="font-story text-2xl font-bold text-text-primary">故事库</h1>
        <p className="mt-1 text-sm text-text-secondary">选择一部已就绪作品，开始新的冒险会话</p>
      </header>

      {isLoading && (
        <div className="flex justify-center py-20 text-text-secondary">
          <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
        </div>
      )}

      {!isLoading && data && data.length === 0 && (
        <p className="rounded-xl border border-border bg-bg-secondary p-8 text-center text-text-secondary">
          暂无可玩作品，请等待管理员完成入库。
        </p>
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
          {data.map((s) => (
            <StoryCard key={s.id} story={s} />
          ))}
        </div>
      )}
    </div>
  );
}
