import { Toaster } from "react-hot-toast";

/** 全局 Toast：继承 :root 语义色，与游玩/管理页对比度一致 */
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
