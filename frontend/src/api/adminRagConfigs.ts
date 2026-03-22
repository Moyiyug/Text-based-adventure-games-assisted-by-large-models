import { apiClient } from "./client";

export interface RagConfigRow {
  id: number;
  name: string;
  variant_type: string;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface RagConfigUpdateBody {
  name?: string | null;
  config?: Record<string, unknown> | null;
}

export const adminRagConfigsApi = {
  list: () => apiClient.get<RagConfigRow[]>("/api/admin/rag-configs"),

  update: (id: number, body: RagConfigUpdateBody) =>
    apiClient.put<RagConfigRow>(`/api/admin/rag-configs/${id}`, body),

  activate: (id: number) =>
    apiClient.post<RagConfigRow>(`/api/admin/rag-configs/${id}/activate`),
};
