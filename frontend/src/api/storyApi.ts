import { apiClient } from "./client";
import type { PlayerStoryDetail, PlayerStoryListItem } from "../types/story";

export async function listStories(): Promise<PlayerStoryListItem[]> {
  const { data } = await apiClient.get<PlayerStoryListItem[]>("/api/stories");
  return data;
}

export async function getStory(storyId: number): Promise<PlayerStoryDetail> {
  const { data } = await apiClient.get<PlayerStoryDetail>(`/api/stories/${storyId}`);
  return data;
}
