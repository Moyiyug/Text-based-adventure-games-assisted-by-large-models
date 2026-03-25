import { Link } from "react-router-dom";
import { BookOpen, PanelLeft, PanelLeftClose } from "lucide-react";
import { UserAccountMenu } from "./UserAccountMenu";

export interface AdminTopBarProps {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
}

/** 管理端顶栏：与 FRONTEND_GUIDELINES 顶栏高度一致（h-14），提供故事库与账号菜单 */
export function AdminTopBar({ sidebarCollapsed, onToggleSidebar }: AdminTopBarProps) {
  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between border-b border-border bg-bg-secondary/95 px-4 backdrop-blur-sm">
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          id="admin-sidebar-toggle"
          aria-expanded={!sidebarCollapsed}
          aria-controls="admin-sidebar"
          title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"}
          onClick={onToggleSidebar}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/30"
        >
          {sidebarCollapsed ? (
            <PanelLeft className="h-5 w-5" aria-hidden />
          ) : (
            <PanelLeftClose className="h-5 w-5" aria-hidden />
          )}
          <span className="sr-only">{sidebarCollapsed ? "展开侧栏" : "收起侧栏"}</span>
        </button>
        <span className="truncate font-story text-sm font-semibold text-text-primary md:text-base">
          RAG Narrative · 管理后台
        </span>
      </div>
      <div className="flex items-center gap-4">
        <Link
          to="/stories"
          className="flex items-center text-sm text-text-secondary transition-colors hover:text-text-primary"
        >
          <BookOpen className="mr-1.5 h-4 w-4 shrink-0" />
          故事库
        </Link>
        <UserAccountMenu showAdminLink={false} />
      </div>
    </header>
  );
}
