import { formatPlainChoiceLabel } from "../../lib/narrativeDisplay";
import { cn } from "../../lib/utils";

interface ChoicePanelProps {
  choices: string[];
  disabled?: boolean;
  freeInputMode: boolean;
  onToggleFreeInput: (free: boolean) => void;
  onSelectChoice: (text: string) => void;
}

export function ChoicePanel({
  choices,
  disabled,
  freeInputMode,
  onToggleFreeInput,
  onSelectChoice,
}: ChoicePanelProps) {
  return (
    <div className="shrink-0 space-y-3 border-t border-border bg-bg-primary/80 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-ui text-sm font-medium text-text-primary">你的选择</span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onToggleFreeInput(!freeInputMode)}
          className={cn(
            "rounded-lg px-3 py-1.5 font-ui text-sm transition-colors",
            freeInputMode
              ? "bg-accent-primary/20 text-accent-primary"
              : "text-text-secondary hover:bg-bg-hover hover:text-text-primary",
            disabled && "pointer-events-none opacity-50"
          )}
        >
          {freeInputMode ? "使用选项" : "自由输入"}
        </button>
      </div>

      {!freeInputMode && choices.length > 0 && (
        <div
          className={cn(
            "flex flex-wrap gap-3 animate-in fade-in duration-200",
            disabled && "opacity-50"
          )}
        >
          {choices.map((c, i) => (
            <button
              key={`${i}-${c.slice(0, 24)}`}
              type="button"
              disabled={disabled}
              onClick={() => onSelectChoice(c)}
              className={cn(
                "min-h-[44px] max-w-full flex-1 basis-[240px] rounded-xl border border-border bg-bg-secondary px-4 py-3 text-left font-ui text-base text-text-primary shadow-sm transition-all",
                "hover:border-accent-primary hover:bg-bg-hover hover:shadow-md",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/30",
                disabled && "cursor-not-allowed opacity-50"
              )}
            >
              {formatPlainChoiceLabel(c)}
            </button>
          ))}
        </div>
      )}

      {!freeInputMode && choices.length === 0 && (
        <p className="font-ui text-sm italic text-text-secondary">
          暂无选项，可切换为自由输入。
        </p>
      )}
    </div>
  );
}
