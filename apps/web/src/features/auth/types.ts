// 文件说明：前端功能模块：types。
export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  default_origin: string | null;
  currency: string;
  language: string;
  created_at: string;
  updated_at: string;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface ProfileUpdate {
  display_name?: string;
  default_origin?: string | null;
  currency?: string;
  language?: string;
}
