import { useEffect, useMemo, useRef } from "react";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { getGlobalProfile, getStoryProfile, importProfileCard } from "../api/profileApi";
import { listMySessions } from "../api/sessionApi";
import { getStory } from "../api/storyApi";
import { Button } from "../components/ui/Button";
import { toast, toastApiError } from "../lib/toast";

function renderJsonObject(obj: Record<string, unknown>, emptyHint: string) {
  const keys = Object.keys(obj);
  if (keys.length === 0) {
    return <p className="text-sm text-text-secondary">{emptyHint}</p>;
  }
  return (
    <dl className="grid gap-2 font-ui text-sm">
      {keys.map((k) => (
        <div key={k} className="rounded-lg border border-border bg-bg-secondary/50 px-3 py-2">
          <dt className="text-xs font-medium text-accent-primary">{k}</dt>
          <dd className="mt-1 break-words text-text-primary">
            {typeof obj[k] === "object"
              ? JSON.stringify(obj[k], null, 0)
              : String(obj[k])}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function ProfilePage() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: global, isLoading: gLoading, error: gError } = useQuery({
    queryKey: ["profile", "global"],
    queryFn: getGlobalProfile,
  });

  const { data: sessions } = useQuery({
    queryKey: ["mySessions"],
    queryFn: listMySessions,
  });

  const storyIds = useMemo(
    () => [...new Set((sessions ?? []).map((s) => s.story_id))],
    [sessions]
  );

  const storyMeta = useQueries({
    queries: storyIds.map((id) => ({
      queryKey: ["story", id] as const,
      queryFn: () => getStory(id),
      enabled: storyIds.length > 0,
    })),
  });

  const storyProfiles = useQueries({
    queries: storyIds.map((id) => ({
      queryKey: ["profile", "story", id] as const,
      queryFn: () => getStoryProfile(id),
      enabled: storyIds.length > 0,
    })),
  });

  useEffect(() => {
    if (gError) toastApiError(gError, "加载画像失败");
  }, [gError]);

  const storySections = useMemo(() => {
    return storyIds.map((id, i) => {
      const title = storyMeta[i]?.data?.title ?? `作品 #${id}`;
      const overrides = storyProfiles[i]?.data?.overrides ?? {};
      const hasOverrides = Object.keys(overrides).length > 0;
      return { id, title, overrides, hasOverrides, loading: storyProfiles[i]?.isLoading };
    });
  }, [storyIds, storyMeta, storyProfiles]);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    try {
      await importProfileCard(f);
      toast.success("角色卡已导入");
      await qc.invalidateQueries({ queryKey: ["profile"] });
    } catch (err) {
      toastApiError(err, "导入失败");
    }
  };

  return (
    <div className="mx-auto min-h-[calc(100vh-3.5rem)] min-w-[1024px] max-w-3xl px-6 py-8">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-story text-2xl font-bold text-text-primary">我的画像</h1>
          <p className="mt-1 text-sm text-text-secondary">
            只读展示；上传 JSON 角色卡可与后端画像合并
          </p>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(ev) => void handleFile(ev)}
          />
          <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
            上传角色卡 JSON
          </Button>
        </div>
      </header>

      {gLoading && (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
        </div>
      )}

      {!gLoading && global && (
        <section className="mb-10">
          <h2 className="mb-3 font-story text-lg font-semibold text-text-primary">
            全局偏好
          </h2>
          {renderJsonObject(
            global.preferences as Record<string, unknown>,
            "暂无全局画像数据（多玩几轮或上传角色卡后会出现）"
          )}
        </section>
      )}

      <section>
        <h2 className="mb-3 font-story text-lg font-semibold text-text-primary">
          作品级覆写
        </h2>
        <p className="mb-4 text-xs text-text-secondary">
          根据你历史会话中出现过的作品列出；仅展示已有覆写键；无数据的作品省略。
        </p>
        <div className="space-y-6">
          {storySections
            .filter((s) => s.hasOverrides)
            .map((s) => (
              <div key={s.id} className="rounded-xl border border-border bg-bg-secondary/40 p-4">
                <h3 className="mb-2 font-ui text-sm font-medium text-text-primary">
                  {s.title}
                </h3>
                {s.loading ? (
                  <Loader2 className="h-5 w-5 animate-spin text-accent-primary" />
                ) : (
                  renderJsonObject(s.overrides as Record<string, unknown>, "无覆写")
                )}
              </div>
            ))}
          {storySections.every((s) => !s.hasOverrides && !s.loading) && (
            <p className="text-sm text-text-secondary">暂无作品级覆写</p>
          )}
        </div>
      </section>
    </div>
  );
}
