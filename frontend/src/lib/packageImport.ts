// Package import — the reverse of package Export (S3, doc 08 §9.1/§10/§14, master
// ref Modül 7 §12). Binds routes/package_import.py:
//   - POST /package-imports (202) — a durable data-queue job that parses a submitted
//     export manifest, re-resolves its dependencies against the local ESP registry and
//     creates a NEW local DRAFT root with origin_package_id provenance. Fresh
//     Idempotency-Key; NO OCC (a submit has no head to race).
//   - GET  /package-imports/{id} — the import report. While the worker runs, status is
//     the transport `queued`/`running`; afterwards it is the terminal outcome
//     (succeeded / blocked / failed). Keyed under ["jobs"] so the job.updated SSE event
//     sweeps it live (INF-11); the poll is the loss-tolerant fallback and stops on a
//     terminal status.
//   - GET  /package-imports — the owner-scoped newest-first import list.
//
// Honest boundary: a `blocked` import DID create a DRAFT root, but it is FAILED-
// validation and never executable — the diagnostics list the unresolved dependencies.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, apiRequest } from "./apiClient";

// POST /package-imports return (commands submit_package_import).
export interface SubmitPackageImportResult {
  import_job_id: string;
  job_id: string;
  queue: string;
  status: string;
}

// GET /package-imports/{id} (queries get_import_report). `diagnostics` carries the
// worker's structured outcome — resolved_count on success, missing_dependencies on a
// blocked import, a structural reason on a failed manifest.
export interface PackageImportReport {
  import_job_id: string;
  status: string;
  package_kind: string;
  manifest_hash: string;
  origin_package_id: string | null;
  origin_revision_id: string | null;
  result_package_root_id: string | null;
  diagnostics: Record<string, unknown> | null;
  job_id: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface PackageImportList {
  items: PackageImportReport[];
}

// Import-report statuses after which polling stops (the worker's terminal outcomes).
export const TERMINAL_PACKAGE_IMPORT_STATUSES: ReadonlySet<string> = new Set([
  "succeeded",
  "blocked",
  "failed",
]);

const IMPORT_POLL_INTERVAL_MS = 5000;

export function packageImportTone(status: string): "ok" | "warn" | "down" | "neutral" {
  if (status === "succeeded") return "ok";
  if (status === "blocked") return "warn";
  if (status === "failed") return "down";
  return "neutral";
}

// Keyed under ["jobs"] so the job.updated SSE event sweeps this query live; the poll
// is the loss-tolerant fallback (INF-11) and stops once the report is terminal.
export function usePackageImportReport(importJobId: string | null) {
  return useQuery({
    queryKey: ["jobs", "package-import", importJobId],
    queryFn: () =>
      api.get<PackageImportReport>(
        `/package-imports/${encodeURIComponent(importJobId ?? "")}`,
      ),
    enabled: importJobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && TERMINAL_PACKAGE_IMPORT_STATUSES.has(status)
        ? false
        : IMPORT_POLL_INTERVAL_MS;
    },
  });
}

export function usePackageImports() {
  return useQuery({
    queryKey: ["package-imports"],
    queryFn: () => api.get<PackageImportList>("/package-imports"),
  });
}

// 202 durable import job on the data queue. The import-job id is the durable handle
// (keep it in view — it survives browser close, CR-09). Fresh Idempotency-Key; NO OCC.
// A successful DRAFT root moves the Library catalog, so invalidate ["library"] too.
export function useSubmitPackageImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (manifest: Record<string, unknown>) =>
      apiRequest<SubmitPackageImportResult>("/package-imports", {
        method: "POST",
        body: { manifest },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["package-imports"] });
      void queryClient.invalidateQueries({ queryKey: ["library"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
