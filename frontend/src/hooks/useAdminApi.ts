import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminMetadataApi } from "../api/adminMetadata";
import {
  adminRagConfigsApi,
  type RagConfigUpdateBody,
} from "../api/adminRagConfigs";
import {
  adminStoriesApi,
  type AdminStoryListItem,
  type IngestionJob,
} from "../api/adminStories";

const qk = {
  stories: (includeDeleted: boolean) => ["admin", "stories", includeDeleted] as const,
  jobs: (storyId: number) => ["admin", "stories", storyId, "ingestion-jobs"] as const,
  warnings: (storyId: number, jobId: number) =>
    ["admin", "stories", storyId, "ingestion-jobs", jobId, "warnings"] as const,
  meta: (storyId: number, resource: string) => ["admin", "metadata", storyId, resource] as const,
  ragConfigs: ["admin", "rag-configs"] as const,
};

export function useAdminStories(includeDeleted = false) {
  return useQuery({
    queryKey: qk.stories(includeDeleted),
    queryFn: async () => {
      const { data } = await adminStoriesApi.list(includeDeleted);
      return data;
    },
    refetchInterval: (query) => {
      const rows = query.state.data as AdminStoryListItem[] | undefined;
      if (rows?.some((s) => s.status === "ingesting")) return 2500;
      return false;
    },
  });
}

export function useUploadStory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) => adminStoriesApi.upload(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "stories"] });
    },
  });
}

export function useUpdateStory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number;
      body: { title?: string; description?: string | null };
    }) => adminStoriesApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "stories"] });
    },
  });
}

export function useDeleteStory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => adminStoriesApi.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "stories"] });
    },
  });
}

export function useTriggerIngest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => adminStoriesApi.ingest(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["admin", "stories"] });
      qc.invalidateQueries({ queryKey: qk.jobs(id) });
    },
  });
}

export function useIngestionJobs(storyId: number | null, options?: { poll?: boolean }) {
  const poll = options?.poll ?? false;
  return useQuery({
    queryKey: storyId != null ? qk.jobs(storyId) : ["admin", "stories", "noop"],
    enabled: storyId != null,
    queryFn: async () => {
      const { data } = await adminStoriesApi.listJobs(storyId!);
      return data;
    },
    refetchInterval: (query) => {
      if (!poll || !query.state.data) return false;
      const jobs = query.state.data as IngestionJob[];
      const active = jobs.some((j) => j.status === "pending" || j.status === "running");
      return active ? 2000 : false;
    },
  });
}

export function useIngestionWarnings(storyId: number | null, jobId: number | null) {
  return useQuery({
    queryKey:
      storyId != null && jobId != null ? qk.warnings(storyId, jobId) : ["admin", "warnings", "noop"],
    enabled: storyId != null && jobId != null,
    queryFn: async () => {
      const { data } = await adminStoriesApi.listJobWarnings(storyId!, jobId!);
      return data;
    },
  });
}

export function useRollbackStory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, targetVersionId }: { id: number; targetVersionId?: number | null }) =>
      adminStoriesApi.rollback(id, targetVersionId),
    onSuccess: (_d, { id }) => {
      qc.invalidateQueries({ queryKey: ["admin", "stories"] });
      qc.invalidateQueries({ queryKey: qk.jobs(id) });
    },
  });
}

function invMeta(qc: ReturnType<typeof useQueryClient>, storyId: number, resource: string) {
  qc.invalidateQueries({ queryKey: qk.meta(storyId, resource) });
}

export function useMetadataEntities(storyId: number | null) {
  return useQuery({
    queryKey: storyId != null ? qk.meta(storyId, "entities") : ["admin", "meta", "noop"],
    enabled: storyId != null,
    queryFn: async () => {
      const { data } = await adminMetadataApi.entities(storyId!);
      return data;
    },
  });
}

export function useEntityMutations(storyId: number) {
  const qc = useQueryClient();
  const inv = () => invMeta(qc, storyId, "entities");
  return {
    create: useMutation({
      mutationFn: (body: Parameters<typeof adminMetadataApi.createEntity>[1]) =>
        adminMetadataApi.createEntity(storyId, body),
      onSuccess: inv,
    }),
    update: useMutation({
      mutationFn: ({
        id,
        body,
      }: {
        id: number;
        body: Parameters<typeof adminMetadataApi.updateEntity>[2];
      }) => adminMetadataApi.updateEntity(storyId, id, body),
      onSuccess: inv,
    }),
    remove: useMutation({
      mutationFn: (id: number) => adminMetadataApi.deleteEntity(storyId, id),
      onSuccess: inv,
    }),
  };
}

export function useMetadataRelationships(storyId: number | null) {
  return useQuery({
    queryKey: storyId != null ? qk.meta(storyId, "relationships") : ["admin", "meta", "noop"],
    enabled: storyId != null,
    queryFn: async () => {
      const { data } = await adminMetadataApi.relationships(storyId!);
      return data;
    },
  });
}

export function useRelationshipMutations(storyId: number) {
  const qc = useQueryClient();
  const inv = () => {
    invMeta(qc, storyId, "relationships");
    invMeta(qc, storyId, "entities");
  };
  return {
    create: useMutation({
      mutationFn: (body: Parameters<typeof adminMetadataApi.createRelationship>[1]) =>
        adminMetadataApi.createRelationship(storyId, body),
      onSuccess: inv,
    }),
    update: useMutation({
      mutationFn: ({
        id,
        body,
      }: {
        id: number;
        body: Parameters<typeof adminMetadataApi.updateRelationship>[2];
      }) => adminMetadataApi.updateRelationship(storyId, id, body),
      onSuccess: inv,
    }),
    remove: useMutation({
      mutationFn: (id: number) => adminMetadataApi.deleteRelationship(storyId, id),
      onSuccess: inv,
    }),
  };
}

export function useMetadataTimeline(storyId: number | null) {
  return useQuery({
    queryKey: storyId != null ? qk.meta(storyId, "timeline") : ["admin", "meta", "noop"],
    enabled: storyId != null,
    queryFn: async () => {
      const { data } = await adminMetadataApi.timeline(storyId!);
      return data;
    },
  });
}

export function useTimelineMutations(storyId: number) {
  const qc = useQueryClient();
  const inv = () => invMeta(qc, storyId, "timeline");
  return {
    create: useMutation({
      mutationFn: (body: Parameters<typeof adminMetadataApi.createTimeline>[1]) =>
        adminMetadataApi.createTimeline(storyId, body),
      onSuccess: inv,
    }),
    update: useMutation({
      mutationFn: ({
        id,
        body,
      }: {
        id: number;
        body: Parameters<typeof adminMetadataApi.updateTimeline>[2];
      }) => adminMetadataApi.updateTimeline(storyId, id, body),
      onSuccess: inv,
    }),
    remove: useMutation({
      mutationFn: (id: number) => adminMetadataApi.deleteTimeline(storyId, id),
      onSuccess: inv,
    }),
  };
}

export function useMetadataChapters(storyId: number | null) {
  return useQuery({
    queryKey: storyId != null ? qk.meta(storyId, "chapters") : ["admin", "meta", "noop"],
    enabled: storyId != null,
    queryFn: async () => {
      const { data } = await adminMetadataApi.chapters(storyId!);
      return data;
    },
  });
}

export function useSceneDetail(storyId: number | null, sceneId: number | null, enabled: boolean) {
  return useQuery({
    queryKey:
      storyId != null && sceneId != null
        ? (["admin", "metadata", storyId, "scene", sceneId] as const)
        : ["admin", "meta", "scene-noop"],
    enabled: Boolean(storyId && sceneId && enabled),
    queryFn: async () => {
      const { data } = await adminMetadataApi.getScene(storyId!, sceneId!);
      return data;
    },
  });
}

export function useChapterSceneMutations(storyId: number) {
  const qc = useQueryClient();
  const inv = () => {
    invMeta(qc, storyId, "chapters");
    invMeta(qc, storyId, "timeline");
    qc.invalidateQueries({ queryKey: ["admin", "metadata", storyId] });
  };
  return {
    updateChapter: useMutation({
      mutationFn: ({
        chapterId,
        body,
      }: {
        chapterId: number;
        body: Parameters<typeof adminMetadataApi.updateChapter>[2];
      }) => adminMetadataApi.updateChapter(storyId, chapterId, body),
      onSuccess: inv,
    }),
    updateScene: useMutation({
      mutationFn: ({
        sceneId,
        body,
      }: {
        sceneId: number;
        body: Parameters<typeof adminMetadataApi.updateScene>[2];
      }) => adminMetadataApi.updateScene(storyId, sceneId, body),
      onSuccess: inv,
    }),
    deleteScene: useMutation({
      mutationFn: (sceneId: number) => adminMetadataApi.deleteScene(storyId, sceneId),
      onSuccess: inv,
    }),
  };
}

export function useMetadataRisk(storyId: number | null) {
  return useQuery({
    queryKey: storyId != null ? qk.meta(storyId, "risk") : ["admin", "meta", "noop"],
    enabled: storyId != null,
    queryFn: async () => {
      const { data } = await adminMetadataApi.riskSegments(storyId!);
      return data;
    },
  });
}

export function useRiskMutations(storyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      segmentId,
      body,
    }: {
      segmentId: number;
      body: { rewritten_text: string };
    }) => adminMetadataApi.updateRiskSegment(storyId, segmentId, body),
    onSuccess: () => invMeta(qc, storyId, "risk"),
  });
}

export function useRagConfigs() {
  return useQuery({
    queryKey: qk.ragConfigs,
    queryFn: async () => {
      const { data } = await adminRagConfigsApi.list();
      return data;
    },
  });
}

export function useUpdateRagConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: RagConfigUpdateBody }) => {
      const { data } = await adminRagConfigsApi.update(id, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.ragConfigs });
    },
  });
}

export function useActivateRagConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await adminRagConfigsApi.activate(id);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.ragConfigs });
    },
  });
}
