import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import { cn } from "../../lib/utils";

export interface ActionMenuItem {
  label: string;
  onSelect: () => void;
  destructive?: boolean;
  disabled?: boolean;
}

export function ActionMenu({ items, ariaLabel = "操作菜单" }: { items: ActionMenuItem[]; ariaLabel?: string }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-bg-secondary text-text-secondary",
          "hover:bg-bg-hover hover:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/30"
        )}
        aria-label={ariaLabel}
      >
        <MoreHorizontal className="h-4 w-4" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          sideOffset={4}
          align="end"
          className="z-[110] min-w-[160px] rounded-lg border border-border bg-bg-secondary p-1 shadow-lg"
        >
          {items.map((item) => (
            <DropdownMenu.Item
              key={item.label}
              disabled={item.disabled}
              onSelect={(e) => {
                e.preventDefault();
                item.onSelect();
              }}
              className={cn(
                "flex h-9 cursor-pointer items-center rounded-md px-2 text-sm outline-none",
                item.destructive
                  ? "text-danger hover:bg-danger/10 focus:bg-danger/10"
                  : "text-text-primary hover:bg-bg-hover focus:bg-bg-hover",
                item.disabled && "pointer-events-none opacity-40"
              )}
            >
              {item.label}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
