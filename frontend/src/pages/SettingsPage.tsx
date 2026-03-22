import { useState, useEffect } from "react";
import type { FormEvent } from "react";
import axios from "axios";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { apiClient } from "../api/client";
import { useAuthStore } from "../stores/authStore";
import type { User } from "../stores/authStore";

export default function SettingsPage() {
  const { user, setUser } = useAuthStore();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
      setBio(user.bio || "");
    }
  }, [user]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);

    if (!displayName.trim()) {
      setError("昵称不能为空");
      return;
    }

    setIsLoading(true);
    try {
      const res = await apiClient.put<User>("/api/users/me/settings", {
        display_name: displayName.trim(),
        bio: bio.trim() || null,
      });
      setUser(res.data);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const d = err.response?.data as { detail?: string } | undefined;
        setError(typeof d?.detail === "string" ? d.detail : "保存失败");
      } else {
        setError("保存失败");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg p-8">
      <h1 className="mb-6 font-story text-2xl text-text-primary">账号设置</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            用户名
          </label>
          <Input type="text" value={user?.username || ""} disabled />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            显示昵称
          </label>
          <Input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="1-30 个字符"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-text-secondary">
            个人简介
          </label>
          <textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder="介绍一下自己..."
            maxLength={500}
            rows={4}
            className="flex w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary transition-colors placeholder:text-text-secondary focus-visible:border-accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20"
          />
        </div>

        {error && (
          <p className="text-sm text-danger">{error}</p>
        )}
        {success && (
          <p className="text-sm text-success">保存成功</p>
        )}

        <Button type="submit" isLoading={isLoading}>
          保存修改
        </Button>
      </form>
    </div>
  );
}
