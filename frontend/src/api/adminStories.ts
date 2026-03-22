import { apiClient } from "./client";

export interface AdminStoryListItem {
  id: number;
  title: string;
  description: string | null;
  status: string;
  source_file_path: string | null;
  version_count: number;
  active_version_id: number | null;
  last_ingested_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryUploadResponse {
  id: number;
  story_version_id: number | null;
  title: string;
  description: string | null;
  source_file_path: string | null;
  status: string;
}

export interface IngestionJob {
  id: number;
  story_id: number;
  story_version_id: number | null;
  status: string;
  progress: number;
  steps_completed: string[];
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface IngestionWarning {
  id: number;
  job_id: number;
  warning_type: string;
  message: string;
  chapter_id: number | null;
  created_at: string;
}

export const adminStoriesApi = {
  list: (includeDeleted?: boolean) =>
    apiClient.get<AdminStoryListItem[]>("/api/admin/stories", {
      params: includeDeleted ? { include_deleted: true } : {},
    }),

  /** 勿手动设置 Content-Type：需由浏览器带上 multipart boundary，否则服务端收不到 file 易 404/422 */
  upload: (form: FormData) =>
    apiClient.post<StoryUploadResponse>("/api/admin/stories/upload", form),

  update: (id: number, body: { title?: string; description?: string | null }) =>
    apiClient.put<StoryUploadResponse>(`/api/admin/stories/${id}`, body),

  remove: (id: number) => apiClient.delete(`/api/admin/stories/${id}`),

  ingest: (id: number) =>
    apiClient.post<{ job_id: number; message?: string }>(`/api/admin/stories/${id}/ingest`),

  listJobs: (storyId: number) =>
    apiClient.get<IngestionJob[]>(`/api/admin/stories/${storyId}/ingestion-jobs`),

  listJobWarnings: (storyId: number, jobId: number) =>
    apiClient.get<IngestionWarning[]>(
      `/api/admin/stories/${storyId}/ingestion-jobs/${jobId}/warnings`
    ),

  rollback: (id: number, targetVersionId?: number | null) =>
    apiClient.post<{ ok: boolean; active_version_id: number; backup_version_id: number | null }>(
      `/api/admin/stories/${id}/rollback`,
      { target_version_id: targetVersionId ?? null }
    ),
};
