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

export interface AdminSidebarProps {
  collapsed: boolean;
}

export function AdminSidebar({ collapsed }: AdminSidebarProps) {
  const location = useLocation();

  return (
    <aside
      id="admin-sidebar"
      aria-label="管理后台导航"
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-border bg-bg-secondary transition-[width] duration-200 ease-out",
        collapsed ? "w-14 overflow-hidden" : "w-56"
      )}
    >
      <div
        className={cn(
          "shrink-0 border-b border-border",
          collapsed ? "flex justify-center py-4" : "px-4 py-5"
        )}
      >
        {!collapsed ? (
          <>
            <p className="font-story text-base font-bold text-text-primary">管理后台</p>
            <p className="mt-1 text-xs text-text-secondary">RAG Narrative Admin</p>
          </>
        ) : (
          <span className="flex flex-col items-center" title="管理后台">
            <Library className="h-5 w-5 text-accent-primary" aria-hidden />
            <span className="sr-only">管理后台</span>
          </span>
        )}
      </div>
      <nav
        className={cn(
          "admin-sidebar-nav flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto",
          collapsed ? "items-center px-1 py-2" : "p-3"
        )}
      >
        {items.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to || location.pathname.startsWith(`${to}/`);
          return (
            <Link
              key={to}
              to={to}
              title={label}
              aria-label={label}
              className={cn(
                "flex items-center rounded-lg text-sm font-medium transition-colors",
                collapsed ? "justify-center p-2.5" : "gap-2 px-3 py-2.5",
                active
                  ? "bg-bg-hover text-text-primary"
                  : "text-text-secondary hover:bg-bg-hover/70 hover:text-text-primary"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {!collapsed ? <span>{label}</span> : null}
            </Link>
          );
        })}
      </nav>
      <div className={cn("shrink-0 border-t border-border", collapsed ? "flex justify-center p-2" : "p-3")}>
        <Link
          to="/stories"
          title="返回故事库"
          aria-label="返回故事库"
          className={cn(
            "flex items-center rounded-lg text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary",
            collapsed ? "justify-center p-2.5" : "gap-2 px-3 py-2.5"
          )}
        >
          <BookOpen className="h-4 w-4 shrink-0" aria-hidden />
          {!collapsed ? "返回故事库" : null}
        </Link>
      </div>
    </aside>
  );
}
