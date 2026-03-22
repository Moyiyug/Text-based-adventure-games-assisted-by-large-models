import { forwardRef, useState } from "react";
import type { InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "../../lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);
    const isPassword = type === "password";
    const currentType = isPassword ? (showPassword ? "text" : "password") : type;

    return (
      <div className="w-full">
        <div className="relative">
          <input
            type={currentType}
            className={cn(
              "flex h-11 w-full rounded-lg border bg-bg-primary px-3 py-2 text-sm text-text-primary font-ui transition-colors placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20",
              error
                ? "border-danger focus-visible:ring-danger/20"
                : "border-border focus-visible:border-accent-primary",
              isPassword && "pr-10",
              className
            )}
            ref={ref}
            {...props}
          />
          {isPassword && (
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary transition-colors"
            >
              {showPassword ? (
                <EyeOff className="h-5 w-5 transition-transform duration-200" />
              ) : (
                <Eye className="h-5 w-5 transition-transform duration-200" />
              )}
            </button>
          )}
        </div>
        {error && (
          <p className="mt-1 text-xs text-danger animate-in slide-in-from-top-1 fade-in duration-200">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
