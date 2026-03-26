/** 与后端 app/schemas/admin_session.py 对齐 */

import type { SessionMessage } from "./session";

export interface AdminSessionListItem {
  id: number;
  user_id: number;
  username: string;
  story_id: number;
  story_title: string;
  story_version_id: number;
  rag_config_id: number;
  mode: string;
  status: string;
  narrative_status: string;
  narrative_plan: Record<string, unknown>;
  turn_count: number;
  opening_goal: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminSessionsListResponse {
  items: AdminSessionListItem[];
  total: number;
}

export interface TranscriptSessionMeta {
  id: number;
  user_id: number;
  story_id: number;
  story_version_id: number;
  rag_config_id: number;
  mode: string;
  status: string;
  narrative_status: string;
  narrative_plan: Record<string, unknown>;
  turn_count: number;
  opening_goal: string;
}

export interface TranscriptResponse {
  session: TranscriptSessionMeta;
  messages: SessionMessage[];
}

export interface AdminUserFeedbackOut {
  id: number;
  session_id: number;
  message_id: number;
  feedback_type: string;
  content: string | null;
  reviewed: boolean;
  created_at?: string | null;
}

export interface FeedbackListResponse {
  items: AdminUserFeedbackOut[];
}
