import { forwardRef } from "react";
import type { TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, disabled, ...props }, ref) => {
    return (
      <div className="w-full">
        <textarea
          ref={ref}
          disabled={disabled}
          className={cn(
            "flex min-h-[120px] w-full resize-y rounded-lg border bg-bg-primary px-3 py-2 text-sm text-text-primary font-ui transition-colors placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20 disabled:cursor-not-allowed disabled:opacity-50",
            error
              ? "border-danger focus-visible:ring-danger/20"
              : "border-border focus-visible:border-accent-primary",
            className
          )}
          {...props}
        />
        {error && (
          <p className="mt-1 text-xs text-danger animate-in slide-in-from-top-1 fade-in duration-200">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";
