import { useState } from "react";
import { Outlet } from "react-router-dom";
import { AdminSidebar } from "./AdminSidebar";
import { AdminTopBar } from "./AdminTopBar";

/** 视口内滚动：主列 min-h-0 避免 flex 撑高整页；语义色与游玩页共用 :root，参见 globals.css */
export function AdminLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen min-h-0 overflow-hidden font-ui">
      <AdminSidebar collapsed={sidebarCollapsed} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-bg-primary">
        <AdminTopBar
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
        />
        <div className="themed-scrollbar min-h-0 flex-1 overflow-y-auto bg-bg-primary">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
