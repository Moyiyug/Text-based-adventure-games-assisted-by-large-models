/** 与后端 PlayerStoryListItem / PlayerStoryDetail 对齐 */

export interface PlayerStoryListItem {
  id: number;
  title: string;
  description: string | null;
  created_at: string;
}

export interface PlayerChapterOutline {
  id: number;
  chapter_number: number;
  title: string | null;
  summary: string | null;
}

export interface PlayerStoryDetail {
  id: number;
  title: string;
  description: string | null;
  chapters: PlayerChapterOutline[];
}
