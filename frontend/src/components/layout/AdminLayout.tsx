import { Outlet } from "react-router-dom";
import { AdminSidebar } from "./AdminSidebar";

/** 布局壳；浅色语义变量由 App.tsx 在 /admin 时为 body 挂上 admin-route，参见 globals.css */
export function AdminLayout() {
  return (
    <div className="flex min-h-screen font-ui">
      <AdminSidebar />
      <div className="min-w-0 flex-1 overflow-auto bg-bg-primary">
        <Outlet />
      </div>
    </div>
  );
}
