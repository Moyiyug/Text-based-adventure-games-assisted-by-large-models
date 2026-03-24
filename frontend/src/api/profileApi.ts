import { apiClient } from "./client";
import type {
  GlobalProfileResponse,
  ProfileImportResponse,
  StoryProfileResponse,
} from "../types/profile";

export async function getGlobalProfile(): Promise<GlobalProfileResponse> {
  const { data } = await apiClient.get<GlobalProfileResponse>("/api/users/me/profile");
  return data;
}

export async function getStoryProfile(storyId: number): Promise<StoryProfileResponse> {
  const { data } = await apiClient.get<StoryProfileResponse>(
    `/api/users/me/profile/story/${storyId}`
  );
  return data;
}

export async function importProfileCard(file: File): Promise<ProfileImportResponse> {
  const body = new FormData();
  body.append("file", file);
  const { data } = await apiClient.post<ProfileImportResponse>(
    "/api/users/me/profile/import",
    body
  );
  return data;
}
