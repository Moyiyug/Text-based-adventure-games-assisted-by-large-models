import { Link, useLocation } from "react-router-dom";
import { BookOpen, History, User as UserIcon } from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../lib/utils";
import { UserAccountMenu } from "./UserAccountMenu";

export function TopNav() {
  const { token } = useAuthStore();
  const location = useLocation();

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
                location.pathname.startsWith("/stories") ||
                  location.pathname.startsWith("/sessions")
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

          <UserAccountMenu showAdminLink />
        </>
      )}
    </nav>
  );
}
