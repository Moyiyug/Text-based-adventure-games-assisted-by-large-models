import { apiClient } from "./client";
import type { User } from "../stores/authStore";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  display_name: string;
}

export const authApi = {
  login: async (data: LoginRequest) => {
    const response = await apiClient.post<TokenResponse>("/api/auth/login", data);
    return response.data;
  },
  register: async (data: RegisterRequest) => {
    const response = await apiClient.post<User>("/api/auth/register", data);
    return response.data;
  },
  logout: async () => {
    await apiClient.post("/api/auth/logout");
  },
  getMe: async () => {
    const response = await apiClient.get<User>("/api/auth/me");
    return response.data;
  },
};
