import { useState } from "react";
import type { FormEvent } from "react";
import axios from "axios";
import { useNavigate, Link, Navigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { authApi } from "../api/auth";
import { useAuthStore } from "../stores/authStore";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());

  if (isAuthenticated) {
    return <Navigate to="/stories" replace />;
  }

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!username) {
      newErrors.username = "请填写用户名";
    } else if (username.length < 3 || username.length > 20 || !/^[a-zA-Z0-9_]+$/.test(username)) {
      newErrors.username = "3-20位，仅字母/数字/下划线";
    }

    if (!displayName) {
      newErrors.displayName = "请填写昵称";
    } else if (displayName.length > 30) {
      newErrors.displayName = "昵称最长30位";
    }

    if (!password) {
      newErrors.password = "请填写密码";
    } else if (password.length < 8) {
      newErrors.password = "密码至少 8 位";
    }

    if (password !== confirmPassword) {
      newErrors.confirmPassword = "两次密码不一致";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsLoading(true);
    try {
      await authApi.register({ username, password, display_name: displayName });
      // Auto login
      const data = await authApi.login({ username, password });
      login(data.access_token, data.user);
      navigate("/stories", { replace: true });
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setErrors({ username: "该用户名已被使用" });
      } else if (axios.isAxiosError(err)) {
        const d = err.response?.data as { detail?: string } | undefined;
        setErrors({
          form: typeof d?.detail === "string" ? d.detail : "注册失败，请稍后重试",
        });
      } else {
        setErrors({ form: "注册失败，请稍后重试" });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center bg-bg-primary py-10">
      <div className="w-[400px] rounded-xl bg-bg-secondary p-10 shadow-2xl">
        <h1 className="mb-2 text-center font-story text-[28px] text-text-primary">
          注册
        </h1>
        <p className="mb-8 text-center font-ui text-sm text-text-secondary">
          创建您的 RAG 账号
        </p>

        {errors.form && (
          <div className="mb-6 animate-in fade-in slide-in-from-top-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-center text-xs text-danger duration-250 ease-out">
            {errors.form}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            type="text"
            placeholder="用户名"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              if (errors.username) setErrors({ ...errors, username: "" });
            }}
            error={errors.username}
          />
          <Input
            type="text"
            placeholder="显示昵称"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              if (errors.displayName) setErrors({ ...errors, displayName: "" });
            }}
            error={errors.displayName}
          />
          <Input
            type="password"
            placeholder="密码"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errors.password) setErrors({ ...errors, password: "" });
            }}
            error={errors.password}
          />
          <Input
            type="password"
            placeholder="确认密码"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (errors.confirmPassword) setErrors({ ...errors, confirmPassword: "" });
            }}
            error={errors.confirmPassword}
          />

          <Button type="submit" className="mt-6 w-full" isLoading={isLoading}>
            注册
          </Button>
        </form>

        <div className="mt-4 text-center text-sm text-text-secondary">
          已有账号？{" "}
          <Link
            to="/login"
            className="text-accent-primary underline hover:brightness-110"
          >
            去登录 →
          </Link>
        </div>
      </div>
    </div>
  );
}
