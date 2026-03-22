import axios from "axios";
import toast from "react-hot-toast";

export { toast };

export function toastApiError(err: unknown, fallback = "请求失败") {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data as { detail?: unknown } | undefined;
    if (typeof d?.detail === "string") {
      toast.error(d.detail);
      return;
    }
  }
  toast.error(fallback);
}
