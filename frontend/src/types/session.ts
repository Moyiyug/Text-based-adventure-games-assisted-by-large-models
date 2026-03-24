/** 与后端 session schemas 对齐 */

export type SessionMode = "strict" | "creative";

export interface SessionMessage {
  id: number;
  turn_number: number;
  role: "user" | "assistant";
  content: string;
  metadata: Record<string, unknown>;
}

export interface SessionStateSnapshot {
  id: number;
  turn_number: number;
  state: NarrativeState;
  created_at?: string | null;
}

/** 叙事状态 JSON（与后端 state.initialize_state 一致） */
export interface NarrativeState {
  current_location?: string;
  active_goal?: string;
  important_items?: unknown[];
  npc_relations?: Record<string, string>;
}

/** 与后端 SessionListItem 对齐（GET /api/sessions） */
export interface SessionListItem {
  id: number;
  story_id: number;
  story_version_id: number;
  rag_config_id: number;
  mode: string;
  status: string;
  turn_count: number;
  opening_goal: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SessionResponse {
  id: number;
  user_id: number;
  story_id: number;
  story_version_id: number;
  rag_config_id: number;
  mode: string;
  opening_goal: string;
  style_config: Record<string, unknown>;
  status: string;
  turn_count: number;
  created_at?: string | null;
  updated_at?: string | null;
  latest_state: SessionStateSnapshot | null;
}

export interface SessionCreatePayload {
  story_id: number;
  mode: SessionMode;
  opening_goal: string;
  rag_config_id?: number | null;
  style_config?: Record<string, unknown> | null;
}

export interface OpeningGenerationResponse {
  narrative: string;
  choices: string[];
  state_update: Record<string, unknown>;
  parse_error: string | null;
}

export interface FeedbackPayload {
  message_id: number;
  feedback_type: string;
  content?: string | null;
}
