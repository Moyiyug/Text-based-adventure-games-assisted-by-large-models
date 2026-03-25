import axios from "axios";
import toast from "react-hot-toast";

export { toast };

/** FastAPI：`detail` 为字符串，或 422 时的 `{ loc, msg, type }[]`。 */
function formatFastApiDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const msg = (item as { msg?: unknown }).msg;
        return typeof msg === "string" ? msg : JSON.stringify(item);
      }
      if (typeof item === "string") return item;
      return JSON.stringify(item);
    });
    return parts.length ? parts.join("；") : null;
  }
  if (detail && typeof detail === "object" && "msg" in detail) {
    const msg = (detail as { msg: unknown }).msg;
    return typeof msg === "string" ? msg : null;
  }
  return null;
}

export function toastApiError(err: unknown, fallback = "请求失败") {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data as { detail?: unknown } | undefined;
    const formatted = d?.detail !== undefined ? formatFastApiDetail(d.detail) : null;
    if (formatted) {
      toast.error(formatted);
      return;
    }
  }
  toast.error(fallback);
}
