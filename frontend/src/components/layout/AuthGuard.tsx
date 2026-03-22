import { Navigate, useLocation, Outlet } from "react-router-dom";
import { useAuthStore } from "../../stores/authStore";

export function AuthGuard({ requireAdmin = false }: { requireAdmin?: boolean }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const isAdmin = useAuthStore((state) => state.isAdmin());
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/stories" replace />;
  }

  return <Outlet />;
}
