// Shared native-file-upload primitive (F-01 Market Data, reused by F-02
// Research Data / F-03). Transfers real file bytes as multipart/form-data —
// fetch has no reliable cross-browser upload-progress event, so this uses
// XMLHttpRequest directly. The server always derives object key, SHA-256
// digest, byte size, and content type from the transferred bytes; callers
// never supply storage metadata.

import { useCallback, useRef, useState } from "react";

import { ApiError, authHeaders, BASE_URL, SESSION_INVALID } from "./apiClient";
import { noteSessionInvalid } from "./session";
import type { ApiErrorResponse } from "./types";

export interface UploadProgress {
  loaded: number;
  total: number;
}

export interface FileUploadHandle<T> {
  promise: Promise<T>;
  cancel: () => void;
}

export interface FileUploadOptions {
  fieldName?: string;
  fields?: Record<string, string>;
  idempotencyKey?: string;
  // Extra request headers (e.g. an ``X-Request-Version`` OCC token). Applied
  // after the auth/idempotency headers so a caller never has to give up an
  // optimistic-concurrency guard just to transfer real bytes.
  headers?: Record<string, string>;
  onProgress?: (progress: UploadProgress) => void;
}

// Real multipart byte transfer with progress reporting and cancellation.
export function uploadFile<T>(
  path: string,
  file: File,
  options: FileUploadOptions = {},
): FileUploadHandle<T> {
  const xhr = new XMLHttpRequest();
  const formData = new FormData();
  formData.append(options.fieldName ?? "file", file, file.name);
  for (const [key, value] of Object.entries(options.fields ?? {})) {
    formData.append(key, value);
  }

  const promise = new Promise<T>((resolve, reject) => {
    xhr.open("POST", `${BASE_URL}${path}`);
    // One credential path for every transport: the shared mode-aware selector
    // (apiClient.authHeaders) — never this module reading both stores and
    // attaching both headers. An upload is a protected request too, so it must
    // send exactly the credential the active AUTH_MODE trusts and nothing else.
    for (const [key, value] of Object.entries(authHeaders())) {
      xhr.setRequestHeader(key, value);
    }
    if (options.idempotencyKey) xhr.setRequestHeader("Idempotency-Key", options.idempotencyKey);
    for (const [key, value] of Object.entries(options.headers ?? {})) {
      xhr.setRequestHeader(key, value);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        options.onProgress?.({ loaded: event.loaded, total: event.total });
      }
    };

    xhr.onload = () => {
      let payload: unknown;
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : undefined;
      } catch {
        payload = undefined;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload as T);
        return;
      }
      const err = (payload as ApiErrorResponse | undefined)?.error;
      const code = err?.code ?? "UNKNOWN";
      // Route a rejected Bearer session through the SAME one-shot stale-session
      // handler as fetch/text requests, so an upload that fails on an expired or
      // revoked token clears the session once and lands the user back on /login —
      // instead of stranding a dead token that would poison every later request.
      // ONLY the canonical invalid-session code clears; a 403/ACCESS_DENIED leaves
      // the (valid) session intact.
      if (code === SESSION_INVALID) noteSessionInvalid();
      reject(new ApiError(xhr.status, code, err?.message ?? xhr.statusText, err?.details ?? []));
    };

    xhr.onerror = () => {
      reject(
        new ApiError(0, "NETWORK_ERROR", "The connection was interrupted. Check your network and retry."),
      );
    };

    xhr.ontimeout = () => {
      reject(new ApiError(0, "NETWORK_ERROR", "The upload timed out. Check your network and retry."));
    };

    xhr.onabort = () => {
      reject(new ApiError(0, "UPLOAD_CANCELLED", "Upload cancelled."));
    };

    xhr.send(formData);
  });

  return { promise, cancel: () => xhr.abort() };
}

export type UploadStatus = "idle" | "uploading" | "success" | "error" | "cancelled";

export interface UseFileUploadResult<T> {
  status: UploadStatus;
  progress: UploadProgress | null;
  error: ApiError | Error | null;
  data: T | null;
  upload: (path: string, file: File, options?: Omit<FileUploadOptions, "onProgress">) => Promise<T>;
  cancel: () => void;
  reset: () => void;
}

// React-hook wrapper around uploadFile(): tracks progress/status/error/data
// state and exposes cancel/reset so a page can show the full upload lifecycle
// (idle -> uploading -> success | error | cancelled) and retry by calling
// upload() again with a fresh File.
export function useFileUpload<T>(): UseFileUploadResult<T> {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [data, setData] = useState<T | null>(null);
  const handleRef = useRef<FileUploadHandle<T> | null>(null);

  const upload = useCallback(
    (path: string, file: File, options: Omit<FileUploadOptions, "onProgress"> = {}) => {
      setStatus("uploading");
      setProgress({ loaded: 0, total: file.size });
      setError(null);
      setData(null);
      const handle = uploadFile<T>(path, file, {
        ...options,
        onProgress: (next) => setProgress(next),
      });
      handleRef.current = handle;
      return handle.promise
        .then((result) => {
          setStatus("success");
          setData(result);
          return result;
        })
        .catch((err: unknown) => {
          const isCancelled = err instanceof ApiError && err.code === "UPLOAD_CANCELLED";
          setStatus(isCancelled ? "cancelled" : "error");
          setError(err instanceof Error ? err : new Error(String(err)));
          throw err;
        })
        .finally(() => {
          handleRef.current = null;
        });
    },
    [],
  );

  const cancel = useCallback(() => {
    handleRef.current?.cancel();
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setProgress(null);
    setError(null);
    setData(null);
  }, []);

  return { status, progress, error, data, upload, cancel, reset };
}
