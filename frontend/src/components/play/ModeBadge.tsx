export function ModeBadge({ mode }: { mode: string }) {
  const strict = mode === "strict";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-ui text-xs font-medium"
      style={
        strict
          ? {
              background: "#1E3A5F",
              color: "#93C5FD",
              border: "1px solid #3B82F6",
            }
          : {
              background: "#3B2F1A",
              color: "#FBBF24",
              border: "1px solid #D4A853",
            }
      }
    >
      <span className="h-2 w-2 rounded-full bg-current opacity-80" aria-hidden />
      {strict ? "严谨模式" : "创作模式"}
    </span>
  );
}
