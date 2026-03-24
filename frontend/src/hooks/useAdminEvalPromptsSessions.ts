import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminEvalApi, type ListEvalRunsParams } from "../api/adminEval";
import { adminPromptsApi } from "../api/adminPrompts";
import { adminSessionsApi, type ListAdminSessionsParams } from "../api/adminSessions";
import type { EvalRunCreate, EvalSampleSessionsRequest } from "../types/eval";
import type { PromptTemplateCreate, PromptTemplateUpdate } from "../types/promptTemplate";

export const adminEvalKeys = {
  runs: (params?: ListEvalRunsParams) => ["admin", "eval", "runs", params ?? {}] as const,
  run: (id: number) => ["admin", "eval", "run", id] as const,
  results: (id: number) => ["admin", "eval", "results", id] as const,
};

export const adminPromptKeys = {
  grouped: ["admin", "prompts", "grouped"] as const,
};

export const adminSessionKeys = {
  list: (params: ListAdminSessionsParams) => ["admin", "sessions", params] as const,
  transcript: (id: number) => ["admin", "sessions", id, "transcript"] as const,
  feedback: (id: number) => ["admin", "sessions", id, "feedback"] as const,
};

export function useEvalRunsList(params?: ListEvalRunsParams) {
  return useQuery({
    queryKey: adminEvalKeys.runs(params),
    queryFn: async () => {
      const { data } = await adminEvalApi.listRuns(params);
      return data;
    },
  });
}

export function useEvalRun(runId: number | null) {
  return useQuery({
    queryKey: runId != null ? adminEvalKeys.run(runId) : ["admin", "eval", "run", "noop"],
    enabled: runId != null,
    queryFn: async () => {
      const { data } = await adminEvalApi.getRun(runId!);
      return data;
    },
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      if (s === "pending" || s === "running") return 2000;
      return false;
    },
  });
}

export function useEvalResults(runId: number | null) {
  return useQuery({
    queryKey: runId != null ? adminEvalKeys.results(runId) : ["admin", "eval", "results", "noop"],
    enabled: runId != null,
    queryFn: async () => {
      const { data } = await adminEvalApi.getResults(runId!);
      return data;
    },
  });
}

export function useStartEvalRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: EvalRunCreate) => {
      const { data } = await adminEvalApi.startRun(body);
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["admin", "eval", "runs"] });
      qc.invalidateQueries({ queryKey: adminEvalKeys.run(data.run_id) });
    },
  });
}

export function useSampleEvalSessions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: EvalSampleSessionsRequest) => {
      const { data } = await adminEvalApi.sampleSessions(body);
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["admin", "eval", "runs"] });
      qc.invalidateQueries({ queryKey: adminEvalKeys.run(data.run_id) });
    },
  });
}

export function usePromptsGrouped() {
  return useQuery({
    queryKey: adminPromptKeys.grouped,
    queryFn: async () => {
      const { data } = await adminPromptsApi.listGrouped();
      return data;
    },
  });
}

export function useUpdatePromptTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: number;
      body: PromptTemplateUpdate;
    }) => {
      const { data } = await adminPromptsApi.update(id, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminPromptKeys.grouped });
    },
  });
}

export function useCreatePromptTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PromptTemplateCreate) => {
      const { data } = await adminPromptsApi.create(body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminPromptKeys.grouped });
    },
  });
}

export function useAdminSessionsList(params: ListAdminSessionsParams) {
  return useQuery({
    queryKey: adminSessionKeys.list(params),
    queryFn: async () => {
      const { data } = await adminSessionsApi.list(params);
      return data;
    },
  });
}

export function useAdminTranscript(sessionId: number | null) {
  return useQuery({
    queryKey:
      sessionId != null
        ? adminSessionKeys.transcript(sessionId)
        : ["admin", "sessions", "transcript", "noop"],
    enabled: sessionId != null,
    queryFn: async () => {
      const { data } = await adminSessionsApi.transcript(sessionId!);
      return data;
    },
  });
}

export function useAdminSessionFeedback(sessionId: number | null) {
  return useQuery({
    queryKey:
      sessionId != null ? adminSessionKeys.feedback(sessionId) : ["admin", "sessions", "fb", "noop"],
    enabled: sessionId != null,
    queryFn: async () => {
      const { data } = await adminSessionsApi.feedback(sessionId!);
      return data;
    },
  });
}
