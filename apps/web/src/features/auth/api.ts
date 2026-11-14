// 文件说明：前端功能模块：api。
import type { AuthSession, ProfileUpdate, UserProfile } from "./types";

import { ApiError, request } from "../../lib/http";

export { ApiError };

export const authApi = {
  register(input: {
    email: string;
    password: string;
    display_name: string;
  }): Promise<AuthSession> {
    return request<AuthSession>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  login(input: { email: string; password: string }): Promise<AuthSession> {
    return request<AuthSession>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  me(token: string): Promise<UserProfile> {
    return request<UserProfile>("/api/v1/auth/me", {}, token);
  },

  updateProfile(token: string, input: ProfileUpdate): Promise<UserProfile> {
    return request<UserProfile>(
      "/api/v1/users/me",
      {
        method: "PATCH",
        body: JSON.stringify(input),
      },
      token,
    );
  },
};
