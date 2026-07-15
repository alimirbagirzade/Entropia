import { vi } from "vitest";

// Route-aware XMLHttpRequest double for lib/upload.ts's uploadFile(), which
// uses XHR (not fetch) so it can report real upload progress. Keys use the
// same "<METHOD> <path fragment>" convention as apiStub.ts's stubApi.
type ShapedResponse = { status?: number; body?: unknown; error?: { code: string; message: string } };
type UploadRouteValue = unknown | ((file: File | null) => unknown);

export interface RecordedUpload {
  url: string;
  headers: Record<string, string>;
  file: File | null;
  // Non-file multipart form fields (e.g. baseline_metadata, expected_stream_version).
  fields: Record<string, string>;
}

function isShapedResponse(value: unknown): value is ShapedResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    ("status" in value || "error" in value) &&
    !("size" in value) // exclude File-like/Blob-shaped values
  );
}

export function stubUpload(routes: Record<string, UploadRouteValue>): { calls: RecordedUpload[] } {
  const calls: RecordedUpload[] = [];

  class FakeXMLHttpRequest {
    method = "GET";
    url = "";
    status = 0;
    statusText = "";
    responseText = "";
    upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    ontimeout: (() => void) | null = null;
    onabort: (() => void) | null = null;
    private headers: Record<string, string> = {};
    private aborted = false;

    open(method: string, url: string) {
      this.method = method.toUpperCase();
      this.url = url;
    }

    setRequestHeader(key: string, value: string) {
      this.headers[key] = value;
    }

    abort() {
      this.aborted = true;
      queueMicrotask(() => this.onabort?.());
    }

    send(body: FormData) {
      const fileEntry = body.get("file");
      const file = fileEntry instanceof File ? fileEntry : null;
      const fields: Record<string, string> = {};
      for (const [key, value] of body.entries()) {
        if (key !== "file" && typeof value === "string") fields[key] = value;
      }
      calls.push({ url: this.url, headers: { ...this.headers }, file, fields });

      queueMicrotask(() => {
        if (this.aborted) return;
        if (file) {
          this.upload.onprogress?.({
            lengthComputable: true,
            loaded: file.size,
            total: file.size,
          } as ProgressEvent);
        }
        const entry = Object.entries(routes).find(([key]) => {
          const spaceAt = key.indexOf(" ");
          return key.slice(0, spaceAt) === this.method && this.url.includes(key.slice(spaceAt + 1));
        });
        if (!entry) {
          this.onerror?.();
          throw new Error(`Unexpected upload: ${this.method} ${this.url}`);
        }
        const raw = entry[1];
        const value = typeof raw === "function" ? (raw as (f: File | null) => unknown)(file) : raw;
        const shaped: ShapedResponse = isShapedResponse(value) ? value : { body: value };
        this.status = shaped.status ?? (shaped.error ? 422 : 200);
        this.statusText = "OK";
        this.responseText = JSON.stringify(shaped.error ? { error: shaped.error } : shaped.body);
        this.onload?.();
      });
    }
  }

  vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest as unknown as typeof XMLHttpRequest);
  return { calls };
}
