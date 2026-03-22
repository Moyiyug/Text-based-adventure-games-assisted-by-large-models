import { apiClient } from "./client";

export interface EntityRow {
  id: number;
  story_version_id: number;
  name: string;
  canonical_name: string;
  entity_type: string;
  description: string | null;
  aliases: string[];
  created_at: string | null;
}

export interface RelationshipRow {
  id: number;
  story_version_id: number;
  entity_a_id: number;
  entity_b_id: number;
  relationship_type: string;
  description: string | null;
  confidence: number;
  created_at: string | null;
}

export interface TimelineRow {
  id: number;
  story_version_id: number;
  event_description: string;
  chapter_id: number | null;
  scene_id: number | null;
  order_index: number;
  participants: number[];
  created_at: string | null;
}

export interface ChapterRow {
  id: number;
  chapter_number: number;
  title: string | null;
  summary: string | null;
  raw_text_preview: string;
  scenes: {
    id: number;
    scene_number: number;
    summary: string | null;
    raw_text_preview: string;
  }[];
}

export interface SceneDetail {
  id: number;
  chapter_id: number;
  scene_number: number;
  raw_text: string;
  summary: string | null;
}

export interface RiskRow {
  id: number;
  story_version_id: number;
  chapter_id: number | null;
  original_text: string;
  rewritten_text: string;
  risk_level: string;
  created_at: string | null;
}

export const adminMetadataApi = {
  entities: (storyId: number) =>
    apiClient.get<EntityRow[]>(`/api/admin/stories/${storyId}/metadata/entities`),
  createEntity: (
    storyId: number,
    body: {
      name: string;
      canonical_name: string;
      entity_type: string;
      description?: string | null;
      aliases?: string[];
    }
  ) => apiClient.post<{ id: number }>(`/api/admin/stories/${storyId}/metadata/entities`, body),
  updateEntity: (
    storyId: number,
    entityId: number,
    body: Partial<{
      name: string;
      canonical_name: string;
      entity_type: string;
      description: string | null;
      aliases: string[];
    }>
  ) => apiClient.put(`/api/admin/stories/${storyId}/metadata/entities/${entityId}`, body),
  deleteEntity: (storyId: number, entityId: number) =>
    apiClient.delete(`/api/admin/stories/${storyId}/metadata/entities/${entityId}`),

  relationships: (storyId: number) =>
    apiClient.get<RelationshipRow[]>(`/api/admin/stories/${storyId}/metadata/relationships`),
  createRelationship: (
    storyId: number,
    body: {
      entity_a_id: number;
      entity_b_id: number;
      relationship_type: string;
      description?: string | null;
      confidence?: number;
    }
  ) =>
    apiClient.post<{ id: number }>(`/api/admin/stories/${storyId}/metadata/relationships`, body),
  updateRelationship: (
    storyId: number,
    relId: number,
    body: Partial<{ relationship_type: string; description: string | null; confidence: number }>
  ) => apiClient.put(`/api/admin/stories/${storyId}/metadata/relationships/${relId}`, body),
  deleteRelationship: (storyId: number, relId: number) =>
    apiClient.delete(`/api/admin/stories/${storyId}/metadata/relationships/${relId}`),

  timeline: (storyId: number) =>
    apiClient.get<TimelineRow[]>(`/api/admin/stories/${storyId}/metadata/timeline`),
  createTimeline: (
    storyId: number,
    body: {
      event_description: string;
      chapter_id?: number | null;
      scene_id?: number | null;
      order_index: number;
      participants?: number[];
    }
  ) => apiClient.post<{ id: number }>(`/api/admin/stories/${storyId}/metadata/timeline`, body),
  updateTimeline: (
    storyId: number,
    eventId: number,
    body: Partial<{
      event_description: string;
      chapter_id: number | null;
      scene_id: number | null;
      order_index: number;
      participants: number[];
    }>
  ) => apiClient.put(`/api/admin/stories/${storyId}/metadata/timeline/${eventId}`, body),
  deleteTimeline: (storyId: number, eventId: number) =>
    apiClient.delete(`/api/admin/stories/${storyId}/metadata/timeline/${eventId}`),

  chapters: (storyId: number) =>
    apiClient.get<ChapterRow[]>(`/api/admin/stories/${storyId}/metadata/chapters`),
  updateChapter: (
    storyId: number,
    chapterId: number,
    body: { title?: string | null; summary?: string | null }
  ) => apiClient.put(`/api/admin/stories/${storyId}/metadata/chapters/${chapterId}`, body),
  getScene: (storyId: number, sceneId: number) =>
    apiClient.get<SceneDetail>(`/api/admin/stories/${storyId}/metadata/scenes/${sceneId}`),
  updateScene: (
    storyId: number,
    sceneId: number,
    body: { summary?: string | null; raw_text?: string }
  ) =>
    apiClient.put<{ ok: boolean; warnings?: string[] }>(
      `/api/admin/stories/${storyId}/metadata/scenes/${sceneId}`,
      body
    ),
  deleteScene: (storyId: number, sceneId: number) =>
    apiClient.delete<{ ok: boolean }>(`/api/admin/stories/${storyId}/metadata/scenes/${sceneId}`),

  riskSegments: (storyId: number) =>
    apiClient.get<RiskRow[]>(`/api/admin/stories/${storyId}/metadata/risk-segments`),
  updateRiskSegment: (storyId: number, segmentId: number, body: { rewritten_text: string }) =>
    apiClient.put(`/api/admin/stories/${storyId}/metadata/risk-segments/${segmentId}`, body),
};
