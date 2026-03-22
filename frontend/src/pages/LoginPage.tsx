import { useState } from "react";
import type { FormEvent } from "react";
import axios from "axios";
import { useNavigate, useLocation, Link, Navigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { authApi } from "../api/auth";
import { useAuthStore } from "../stores/authStore";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());

  if (isAuthenticated) {
    return <Navigate to="/stories" replace />;
  }

  const from = location.state?.from?.pathname || "/stories";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username || !password) {
      setError("请填写用户名和密码");
      return;
    }

    setIsLoading(true);
    try {
      const data = await authApi.login({ username, password });
      login(data.access_token, data.user);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const d = err.response?.data as { detail?: string } | undefined;
        setError(typeof d?.detail === "string" ? d.detail : "用户名或密码错误");
      } else {
        setError("用户名或密码错误");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center bg-bg-primary">
      <div className="w-[400px] rounded-xl bg-bg-secondary p-10 shadow-2xl">
        <h1 className="mb-2 text-center font-story text-[28px] text-text-primary">
          登录
        </h1>
        <p className="mb-8 text-center font-ui text-sm text-text-secondary">
          欢迎回到 RAG 交互式叙事冒险平台
        </p>

        {error && (
          <div className="mb-6 animate-in fade-in slide-in-from-top-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-center text-xs text-danger duration-250 ease-out">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            type="text"
            placeholder="用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <Input
            type="password"
            placeholder="密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Button type="submit" className="mt-6 w-full" isLoading={isLoading}>
            登录
          </Button>
        </form>

        <div className="mt-4 text-center text-sm text-text-secondary">
          没有账号？{" "}
          <Link
            to="/register"
            className="text-accent-primary underline hover:brightness-110"
          >
            去注册 →
          </Link>
        </div>
      </div>
    </div>
  );
}
