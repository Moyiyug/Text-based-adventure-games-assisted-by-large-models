import { apiClient } from "./client";
import type {
  EvalResultOut,
  EvalResultsListResponse,
  EvalRunCreate,
  EvalRunOut,
  EvalRunsListResponse,
  EvalRunTriggerResponse,
  EvalSampleSessionsRequest,
} from "../types/eval";

export interface ListEvalRunsParams {
  story_version_id?: number;
  status?: string;
  limit?: number;
  offset?: number;
}

export const adminEvalApi = {
  startRun: (body: EvalRunCreate) =>
    apiClient.post<EvalRunTriggerResponse>("/api/admin/eval/runs", body),

  sampleSessions: (body: EvalSampleSessionsRequest) =>
    apiClient.post<EvalRunTriggerResponse>("/api/admin/eval/sample-sessions", body),

  listRuns: (params?: ListEvalRunsParams) =>
    apiClient.get<EvalRunsListResponse>("/api/admin/eval/runs", { params }),

  getRun: (runId: number) => apiClient.get<EvalRunOut>(`/api/admin/eval/runs/${runId}`),

  getResults: (runId: number) =>
    apiClient.get<EvalResultsListResponse>(`/api/admin/eval/runs/${runId}/results`),
};

export type { EvalResultOut };
