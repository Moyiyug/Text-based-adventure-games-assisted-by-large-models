import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import type { NarrativeState } from "../../types/session";
import { cn } from "../../lib/utils";

interface StatePanelProps {
  state: NarrativeState | null;
  highlightKeys: string[];
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md bg-bg-hover px-2 py-1 font-ui text-xs text-text-primary">
      {children}
    </span>
  );
}

function npcDotClass(relation: string): string {
  const r = relation.toLowerCase();
  if (r.includes("友") || r.includes("善")) return "bg-accent-secondary";
  if (r.includes("敌") || r.includes("恶")) return "bg-danger";
  if (r.includes("中")) return "bg-warning";
  return "bg-text-secondary";
}

export function StatePanel({ state, highlightKeys }: StatePanelProps) {
  const [collapsed, setCollapsed] = useState(true);

  const loc = state?.current_location?.trim() || "";
  const goal = state?.active_goal?.trim() || "";
  const items = Array.isArray(state?.important_items) ? state!.important_items! : [];
  const npcs = state?.npc_relations && typeof state.npc_relations === "object"
    ? Object.entries(state.npc_relations)
    : [];

  const hl = (key: string) => highlightKeys.includes(key);

  const row = (
    key: string,
    label: string,
    icon: string,
    content: React.ReactNode,
    empty: string
  ) => (
    <div
      className={cn(
        "rounded-lg px-2 py-2 transition-colors duration-300 ease-out",
        hl(key) && "bg-accent-primary/20"
      )}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-xs" aria-hidden>
          {icon}
        </span>
        <span className="font-ui text-xs text-text-secondary">{label}</span>
      </div>
      <div className="mt-1 pl-5">
        {content ? (
          content
        ) : (
          <span className="font-ui text-sm italic text-text-secondary">{empty}</span>
        )}
      </div>
    </div>
  );

  return (
    <aside
      className={cn(
        "flex h-full min-h-0 shrink-0 flex-col border-l border-border bg-bg-secondary transition-[width] duration-200 ease-out",
        collapsed ? "w-12" : "w-[280px]"
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex h-12 w-full items-center justify-between border-b border-border px-3 font-ui text-sm font-medium text-text-primary hover:bg-bg-hover"
        aria-expanded={!collapsed}
      >
        {!collapsed && <span>状态面板</span>}
        <ChevronLeft
          className={cn(
            "h-5 w-5 shrink-0 text-text-secondary transition-transform duration-200",
            collapsed && "rotate-180"
          )}
        />
      </button>

      {!collapsed && (
        <div className="flex flex-1 flex-col gap-0 overflow-y-auto p-3">
          {row(
            "current_location",
            "当前位置",
            "📍",
            loc ? (
              <p className="font-ui text-sm text-text-primary">{loc}</p>
            ) : null,
            "未知"
          )}
          <div className="my-3 h-px bg-border" />
          {row(
            "active_goal",
            "当前目标",
            "🎯",
            goal ? (
              <p className="line-clamp-2 font-ui text-sm text-text-primary">{goal}</p>
            ) : null,
            "无特定目标"
          )}
          <div className="my-3 h-px bg-border" />
          {row(
            "important_items",
            "关键物品",
            "🎒",
            items.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {items.slice(0, 12).map((it, i) => (
                  <Tag key={i}>{String(it)}</Tag>
                ))}
              </div>
            ) : null,
            "暂无物品"
          )}
          <div className="my-3 h-px bg-border" />
          {row(
            "npc_relations",
            "NPC 关系",
            "👥",
            npcs.length > 0 ? (
              <ul className="space-y-3">
                {npcs.map(([name, rel]) => (
                  <li key={name}>
                    <div className="font-ui text-sm font-medium text-text-primary">{name}</div>
                    <div className="mt-0.5 flex items-start gap-2 font-ui text-xs text-text-secondary">
                      <span
                        className={cn(
                          "mt-1 h-2 w-2 shrink-0 rounded-full",
                          npcDotClass(String(rel))
                        )}
                      />
                      {rel}
                    </div>
                  </li>
                ))}
              </ul>
            ) : null,
            "尚未遇见 NPC"
          )}
        </div>
      )}
    </aside>
  );
}
