import { cn } from "../../lib/utils";

export type BadgeVariant = "default" | "success" | "warning" | "danger" | "muted";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        {
          "bg-bg-hover text-text-secondary": variant === "default",
          "bg-accent-secondary/15 text-accent-secondary": variant === "success",
          "bg-warning/15 text-warning": variant === "warning",
          "bg-danger/15 text-danger": variant === "danger",
          "bg-border/50 text-text-secondary": variant === "muted",
        },
        className
      )}
    >
      {children}
    </span>
  );
}
