// Shared API types mirroring the backend canonical envelopes (Module 19).

export interface ApiErrorBody {
  code: string;
  message: string;
  details: Array<Record<string, unknown>>;
  request_id?: string | null;
  correlation_id?: string | null;
}

export interface ApiErrorResponse {
  error: ApiErrorBody;
}

export interface PageMeta {
  cursor?: string | null;
  has_more: boolean;
  total?: number | null;
}

export interface Page<T> {
  data: T[];
  meta: PageMeta;
}

export interface Meta {
  name: string;
  version: string;
  environment: string;
  api_base_path: string;
}

export interface ReadyResponse {
  status: string;
  checks: Record<string, string>;
}

export interface Me {
  principal_id: string | null;
  principal_type: string;
  role: string | null;
  is_admin: boolean;
  is_authenticated: boolean;
}

// Local-auth envelopes (M1 §4). Sign Up can never assert a role; the server
// assigns the baseline role and echoes it back here.
export interface AuthUser {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
}

export type SignUpResponse = AuthUser;

export interface LoginResponse {
  token: string;
  session_id: string;
  expires_at: string;
  user: AuthUser;
}
