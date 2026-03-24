import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { TopNav } from "./components/layout/TopNav";
import { AuthGuard } from "./components/layout/AuthGuard";
import { AdminGuard } from "./components/layout/AdminGuard";
import { AdminLayout } from "./components/layout/AdminLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import SettingsPage from "./pages/SettingsPage";
import AdminStoriesPage from "./pages/admin/AdminStoriesPage";
import AdminMetadataPage from "./pages/admin/AdminMetadataPage";
import AdminRagConfigPage from "./pages/admin/AdminRagConfigPage";
import AdminEvalPage from "./pages/admin/AdminEvalPage";
import AdminPromptsPage from "./pages/admin/AdminPromptsPage";
import AdminSessionsPage from "./pages/admin/AdminSessionsPage";
import { AppToaster } from "./components/ui/AppToaster";
import StoryLibraryPage from "./pages/StoryLibraryPage";
import NewSessionPage from "./pages/NewSessionPage";
import PlaySessionPage from "./pages/PlaySessionPage";
import SessionHistoryPage from "./pages/SessionHistoryPage";
import SessionReplayPage from "./pages/SessionReplayPage";
import ProfilePage from "./pages/ProfilePage";

/** 管理端 Radix Portal 挂在 body 下，需让 body 继承浅色语义变量，避免弹层/下拉回到深色令牌 */
function useAdminBodyClass() {
  const { pathname } = useLocation();
  useEffect(() => {
    const on = pathname.startsWith("/admin");
    document.body.classList.toggle("admin-route", on);
    return () => document.body.classList.remove("admin-route");
  }, [pathname]);
}

function AppRoutes() {
  useAdminBodyClass();
  const location = useLocation();
  const hideTopNav = location.pathname.startsWith("/admin");

  return (
    <>
      {!hideTopNav && <TopNav />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<AuthGuard />}>
          <Route path="/" element={<Navigate to="/stories" replace />} />
          <Route path="/stories" element={<StoryLibraryPage />} />
          <Route path="/stories/:storyId/new-session" element={<NewSessionPage />} />
          <Route path="/sessions/:sessionId" element={<PlaySessionPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/history" element={<SessionHistoryPage />} />
          <Route path="/history/:sessionId" element={<SessionReplayPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>

        <Route element={<AdminGuard />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<Navigate to="/admin/stories" replace />} />
            <Route path="/admin/stories" element={<AdminStoriesPage />} />
            <Route path="/admin/metadata" element={<AdminMetadataPage />} />
            <Route path="/admin/rag-config" element={<AdminRagConfigPage />} />
            <Route path="/admin/prompts" element={<AdminPromptsPage />} />
            <Route path="/admin/eval" element={<AdminEvalPage />} />
            <Route path="/admin/sessions" element={<AdminSessionsPage />} />
          </Route>
        </Route>
      </Routes>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg-primary font-ui text-text-primary">
        <AppRoutes />
      </div>
      <AppToaster />
    </BrowserRouter>
  );
}

export default App;
