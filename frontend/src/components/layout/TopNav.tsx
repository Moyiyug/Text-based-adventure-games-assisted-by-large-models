import { Link, useLocation, useNavigate } from "react-router-dom";
import { BookOpen, History, User as UserIcon, LogOut, Settings, Shield } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useAuthStore } from "../../stores/authStore";
import { authApi } from "../../api/auth";
import { cn } from "../../lib/utils";

export function TopNav() {
  const { token, user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore error
    } finally {
      logout();
      navigate("/login");
    }
  };

  return (
    <nav className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-border bg-bg-secondary/80 px-6 backdrop-blur-sm">
      <Link
        to={token ? "/stories" : "/login"}
        className="font-story text-xl font-bold text-text-primary"
      >
        RAG Narrative
      </Link>

      {!token ? (
        <div className="flex items-center space-x-4">
          <Link
            to="/login"
            className={cn(
              "text-sm font-ui transition-colors duration-150 hover:text-text-primary",
              location.pathname === "/login"
                ? "text-text-primary border-b-2 border-accent-primary pb-1"
                : "text-text-secondary"
            )}
          >
            登录
          </Link>
          <Link
            to="/register"
            className={cn(
              "text-sm font-ui transition-colors duration-150 hover:text-text-primary",
              location.pathname === "/register"
                ? "text-text-primary border-b-2 border-accent-primary pb-1"
                : "text-text-secondary"
            )}
          >
            注册
          </Link>
        </div>
      ) : (
        <>
          <div className="flex items-center space-x-6">
            <Link
              to="/stories"
              className={cn(
                "flex items-center text-sm font-ui transition-colors duration-150 hover:text-text-primary",
                location.pathname.startsWith("/stories")
                  ? "text-text-primary border-b-2 border-accent-primary pb-1"
                  : "text-text-secondary"
              )}
            >
              <BookOpen className="mr-1.5 h-4 w-4" />
              故事库
            </Link>
            <Link
              to="/history"
              className={cn(
                "flex items-center text-sm font-ui transition-colors duration-150 hover:text-text-primary",
                location.pathname.startsWith("/history")
                  ? "text-text-primary border-b-2 border-accent-primary pb-1"
                  : "text-text-secondary"
              )}
            >
              <History className="mr-1.5 h-4 w-4" />
              历史
            </Link>
            <Link
              to="/profile"
              className={cn(
                "flex items-center text-sm font-ui transition-colors duration-150 hover:text-text-primary",
                location.pathname.startsWith("/profile")
                  ? "text-text-primary border-b-2 border-accent-primary pb-1"
                  : "text-text-secondary"
              )}
            >
              <UserIcon className="mr-1.5 h-4 w-4" />
              画像
            </Link>
          </div>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="flex h-8 w-8 items-center justify-center rounded-full bg-bg-hover text-sm font-medium text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20">
              {user?.display_name.charAt(0).toUpperCase()}
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={8}
                className="w-44 rounded-lg bg-bg-secondary shadow-lg border border-border p-1 animate-in fade-in zoom-in-95 duration-150"
              >
                <DropdownMenu.Item
                  onClick={() => navigate("/settings")}
                  className="flex h-9 cursor-pointer items-center rounded-md px-2 text-sm text-text-primary outline-none hover:bg-bg-hover focus:bg-bg-hover"
                >
                  <Settings className="mr-2 h-4 w-4" />
                  账号设置
                </DropdownMenu.Item>
                {user?.role === "admin" && (
                  <DropdownMenu.Item
                    onClick={() => navigate("/admin")}
                    className="flex h-9 cursor-pointer items-center rounded-md px-2 text-sm text-text-primary outline-none hover:bg-bg-hover focus:bg-bg-hover"
                  >
                    <Shield className="mr-2 h-4 w-4" />
                    管理后台
                  </DropdownMenu.Item>
                )}
                <DropdownMenu.Separator className="my-1 h-px bg-border" />
                <DropdownMenu.Item
                  onClick={handleLogout}
                  className="flex h-9 cursor-pointer items-center rounded-md px-2 text-sm text-danger outline-none hover:bg-bg-hover focus:bg-bg-hover"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </>
      )}
    </nav>
  );
}
