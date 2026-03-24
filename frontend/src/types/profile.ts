/** 与后端 app/schemas/profile.py 对齐 */

export interface GlobalProfileResponse {
  preferences: Record<string, unknown>;
}

export interface StoryProfileResponse {
  story_id: number;
  overrides: Record<string, unknown>;
}

export interface ProfileImportResponse {
  scope: "global" | "story";
  preferences: Record<string, unknown>;
  story_id?: number | null;
  overrides: Record<string, unknown>;
}
