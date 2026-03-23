import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { Badge } from "../ui/Badge";
import type { PlayerStoryListItem } from "../../types/story";
import { cn } from "../../lib/utils";

function formatRelative(iso: string): string {
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    const day = 86400000;
    if (diff < day) return "今日";
    if (diff < 2 * day) return "昨日";
    return d.toLocaleDateString();
  } catch {
    return "—";
  }
}

export interface StoryCardProps {
  story: PlayerStoryListItem;
  className?: string;
}

export function StoryCard({ story, className }: StoryCardProps) {
  return (
    <Link
      to={`/stories/${story.id}/new-session`}
      className={cn(
        "group flex flex-col rounded-xl border border-border bg-bg-secondary p-4 transition-colors hover:border-accent-primary/40 hover:bg-bg-hover/50 min-h-[220px]",
        className
      )}
    >
      <div className="flex flex-1 gap-4">
        <div className="flex h-20 w-16 shrink-0 items-center justify-center rounded-lg bg-bg-primary text-accent-primary">
          <BookOpen className="h-9 w-9 opacity-80" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-story text-lg font-semibold text-text-primary line-clamp-2 group-hover:text-accent-primary transition-colors">
            {story.title}
          </h3>
          <p className="mt-2 text-sm text-text-secondary line-clamp-3">
            {story.description?.trim() || "暂无简介"}
          </p>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-text-secondary">
        <span>{formatRelative(story.created_at)}</span>
        <Badge variant="success">已就绪</Badge>
      </div>
    </Link>
  );
}
