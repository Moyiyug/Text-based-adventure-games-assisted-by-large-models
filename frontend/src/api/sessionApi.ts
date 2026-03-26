import { apiClient } from "./client";
import type {
  FeedbackPayload,
  OpeningGenerationResponse,
  SessionCreatePayload,
  SessionListItem,
  SessionMessage,
  SessionResponse,
  SessionStateSnapshot,
} from "../types/session";

export async function listMySessions(): Promise<SessionListItem[]> {
  const { data } = await apiClient.get<SessionListItem[]>("/api/sessions");
  return data;
}

export async function createSession(body: SessionCreatePayload): Promise<SessionResponse> {
  const { data } = await apiClient.post<SessionResponse>("/api/sessions", body);
  return data;
}

export async function getSession(sessionId: number): Promise<SessionResponse> {
  const { data } = await apiClient.get<SessionResponse>(`/api/sessions/${sessionId}`);
  return data;
}

export async function getSessionMessages(sessionId: number): Promise<SessionMessage[]> {
  const { data } = await apiClient.get<SessionMessage[]>(`/api/sessions/${sessionId}/messages`);
  return data;
}

export async function getSessionState(sessionId: number): Promise<SessionStateSnapshot> {
  const { data } = await apiClient.get<SessionStateSnapshot>(`/api/sessions/${sessionId}/state`);
  return data;
}

export async function postOpening(sessionId: number): Promise<OpeningGenerationResponse> {
  const { data } = await apiClient.post<OpeningGenerationResponse>(
    `/api/sessions/${sessionId}/opening`
  );
  return data;
}

/** 同一 sessionId 进行中的开场请求合并为单条 HTTP，避免 Strict Mode 双挂载重复 POST。 */
const openingInflight = new Map<number, Promise<OpeningGenerationResponse>>();
const openingDedupeListeners = new Map<number, Set<() => void>>();

function notifyOpeningDedupe(sessionId: number) {
  openingDedupeListeners.get(sessionId)?.forEach((cb) => cb());
}

/** 供 useSyncExternalStore：当前会话是否有进行中的开场请求（含去重合并）。 */
export function subscribeOpeningDedupe(sessionId: number, onStoreChange: () => void) {
  let set = openingDedupeListeners.get(sessionId);
  if (!set) {
    set = new Set();
    openingDedupeListeners.set(sessionId, set);
  }
  set.add(onStoreChange);
  return () => {
    set!.delete(onStoreChange);
    if (set!.size === 0) {
      openingDedupeListeners.delete(sessionId);
    }
  };
}

export function getOpeningDedupePending(sessionId: number): boolean {
  return openingInflight.has(sessionId);
}

export async function postOpeningDeduped(sessionId: number): Promise<OpeningGenerationResponse> {
  const existing = openingInflight.get(sessionId);
  if (existing) return existing;
  notifyOpeningDedupe(sessionId);
  const p = postOpening(sessionId).finally(() => {
    openingInflight.delete(sessionId);
    notifyOpeningDedupe(sessionId);
  });
  openingInflight.set(sessionId, p);
  notifyOpeningDedupe(sessionId);
  return p;
}

export async function postFeedback(sessionId: number, body: FeedbackPayload): Promise<unknown> {
  const { data } = await apiClient.post(`/api/sessions/${sessionId}/feedback`, body);
  return data;
}

export async function archiveSession(sessionId: number): Promise<SessionResponse> {
  const { data } = await apiClient.post<SessionResponse>(`/api/sessions/${sessionId}/archive`);
  return data;
}

export async function resumeSession(sessionId: number): Promise<SessionResponse> {
  const { data } = await apiClient.post<SessionResponse>(`/api/sessions/${sessionId}/resume`);
  return data;
}

export async function deleteSession(sessionId: number): Promise<void> {
  await apiClient.delete(`/api/sessions/${sessionId}`);
}
