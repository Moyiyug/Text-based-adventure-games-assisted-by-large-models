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
