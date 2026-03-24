import { Link, useLocation } from "react-router-dom";
import {
  BookOpen,
  ClipboardList,
  Database,
  FileCode2,
  FlaskConical,
  Library,
  SlidersHorizontal,
} from "lucide-react";
import { cn } from "../../lib/utils";

const items = [
  { to: "/admin/stories", label: "作品与入库", icon: Library },
  { to: "/admin/metadata", label: "元数据编辑", icon: Database },
  { to: "/admin/prompts", label: "提示词编辑", icon: FileCode2 },
  { to: "/admin/rag-config", label: "RAG 方案配置", icon: SlidersHorizontal },
  { to: "/admin/eval", label: "评测面板", icon: FlaskConical },
  { to: "/admin/sessions", label: "会话查看", icon: ClipboardList },
];

export function AdminSidebar() {
  const location = useLocation();

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-bg-secondary">
      <div className="border-b border-border px-4 py-5">
        <p className="font-story text-base font-bold text-text-primary">管理后台</p>
        <p className="mt-1 text-xs text-text-secondary">RAG Narrative Admin</p>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {items.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to || location.pathname.startsWith(`${to}/`);
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-bg-hover text-text-primary"
                  : "text-text-secondary hover:bg-bg-hover/70 hover:text-text-primary"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-3">
        <Link
          to="/stories"
          className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        >
          <BookOpen className="h-4 w-4" />
          返回故事库
        </Link>
      </div>
    </aside>
  );
}
