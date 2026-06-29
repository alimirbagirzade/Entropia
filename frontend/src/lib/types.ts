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
