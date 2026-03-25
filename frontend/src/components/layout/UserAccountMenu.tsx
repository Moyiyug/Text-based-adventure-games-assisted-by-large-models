import { useNavigate } from "react-router-dom";
import { LogOut, Settings, Shield } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useAuthStore } from "../../stores/authStore";
import { authApi } from "../../api/auth";

export interface UserAccountMenuProps {
  /** 在管理端顶栏可设为 false，避免重复「管理后台」入口 */
  showAdminLink?: boolean;
}

export function UserAccountMenu({ showAdminLink = true }: UserAccountMenuProps) {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  if (!user) return null;

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
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="flex h-8 w-8 items-center justify-center rounded-full bg-bg-hover text-sm font-medium text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20">
        {user.display_name.charAt(0).toUpperCase()}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="w-44 rounded-lg border border-border bg-bg-secondary p-1 shadow-lg animate-in fade-in zoom-in-95 duration-150"
        >
          <DropdownMenu.Item
            onClick={() => navigate("/settings")}
            className="flex h-9 cursor-pointer items-center rounded-md px-2 text-sm text-text-primary outline-none hover:bg-bg-hover focus:bg-bg-hover"
          >
            <Settings className="mr-2 h-4 w-4" />
            账号设置
          </DropdownMenu.Item>
          {showAdminLink && user.role === "admin" && (
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
  );
}
