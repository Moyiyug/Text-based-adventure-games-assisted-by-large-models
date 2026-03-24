import { apiClient } from "./client";
import type {
  AdminSessionsListResponse,
  FeedbackListResponse,
  TranscriptResponse,
} from "../types/adminSession";

export interface ListAdminSessionsParams {
  user_id?: number;
  story_id?: number;
  status?: string;
  limit?: number;
  offset?: number;
}

export const adminSessionsApi = {
  list: (params?: ListAdminSessionsParams) =>
    apiClient.get<AdminSessionsListResponse>("/api/admin/sessions", { params }),

  transcript: (sessionId: number) =>
    apiClient.get<TranscriptResponse>(`/api/admin/sessions/${sessionId}/transcript`),

  feedback: (sessionId: number) =>
    apiClient.get<FeedbackListResponse>(`/api/admin/sessions/${sessionId}/feedback`),
};
