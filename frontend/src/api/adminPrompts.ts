import { apiClient } from "./client";
import type {
  PromptTemplateCreate,
  PromptTemplateUpdate,
  PromptTemplatesGroupedResponse,
  PromptTemplateAdminOut,
} from "../types/promptTemplate";

export const adminPromptsApi = {
  listGrouped: () => apiClient.get<PromptTemplatesGroupedResponse>("/api/admin/prompts"),

  update: (templateId: number, body: PromptTemplateUpdate) =>
    apiClient.put<PromptTemplateAdminOut>(`/api/admin/prompts/${templateId}`, body),

  create: (body: PromptTemplateCreate) =>
    apiClient.post<PromptTemplateAdminOut>("/api/admin/prompts", body),
};
