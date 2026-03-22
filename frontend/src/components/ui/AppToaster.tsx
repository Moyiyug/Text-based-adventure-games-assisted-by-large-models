import { Toaster } from "react-hot-toast";

/** 全局 Toast：与 .admin / 默认主题下的文字对比度协调 */
export function AppToaster() {
  return (
    <Toaster
      position="top-center"
      toastOptions={{
        duration: 4000,
        className: "!bg-bg-secondary !text-text-primary !border !border-border !rounded-lg !shadow-lg !font-ui !text-sm",
        success: { iconTheme: { primary: "var(--accent-secondary)", secondary: "var(--bg-secondary)" } },
        error: { iconTheme: { primary: "var(--danger)", secondary: "var(--bg-secondary)" } },
      }}
    />
  );
}
