import { AuthGuard } from "./AuthGuard";

/** 管理员路由壳：与 AuthGuard requireAdmin 等价，语义对应 IMPLEMENTATION_PLAN §2.13 */
export function AdminGuard() {
  return <AuthGuard requireAdmin />;
}
