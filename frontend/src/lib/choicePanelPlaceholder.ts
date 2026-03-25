/**
 * 游玩页选项区定稿前占位（F16 / FRONTEND_GUIDELINES §6.3）。
 * 叙事 token 仍在追加时用「叙事生成中…」；正文足够长后仍无 choices 时用「生成选项…」。
 */

/** 认为流式叙事已「明显开始」的最小字符数（启发式，无需改 SSE） */
export const STREAMING_NARRATIVE_THRESHOLD_CHARS = 48;

export type ChoicePanelStreamHint = "narrative" | "awaiting_choices";

export function choicePanelStreamHint(
  streaming: boolean,
  streamingNarrativeCharCount: number
): ChoicePanelStreamHint | null {
  if (!streaming) return null;
  if (streamingNarrativeCharCount < STREAMING_NARRATIVE_THRESHOLD_CHARS) {
    return "narrative";
  }
  return "awaiting_choices";
}
