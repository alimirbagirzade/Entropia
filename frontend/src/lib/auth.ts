// Real-auth flows (Master §20 / M1 §4): login, signup (auto-login), logout, and a
// reactive hook for the current session token. Endpoints are the source of truth;
// on success we persist the opaque Bearer token and invalidate all queries so
// identity-dependent views (`/me`, role-gated nav) refetch under the new principal.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { api } from "./apiClient";
import { clearSession, getSessionToken, setSession, subscribe } from "./session";
import type { LoginResponse, SignUpResponse } from "./types";

export function useSessionToken(): string | null {
  return useSyncExternalStore(subscribe, getSessionToken, getSessionToken);
}

export interface Credentials {
  username: string;
  password: string;
}

export interface SignupInput extends Credentials {
  email?: string;
  display_name?: string;
}

async function loginRequest(creds: Credentials): Promise<LoginResponse> {
  const result = await api.post<LoginResponse>("/auth/login", creds);
  setSession({ token: result.token, user: result.user, expiresAt: result.expires_at });
  return result;
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: loginRequest,
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useSignup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SignupInput): Promise<LoginResponse> => {
      // Signup can never escalate (no role field); the server always assigns the
      // baseline role. Auto-login lands the new user straight into a session.
      await api.post<SignUpResponse>("/auth/signup", input);
      return loginRequest({ username: input.username, password: input.password });
    },
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<void> => {
      // Best-effort revoke: a failed/expired server call must never strand the
      // user in a half-logged-in UI, so the local session is cleared regardless.
      try {
        await api.post<{ session_id: string; revoked: boolean }>("/auth/logout");
      } catch {
        // swallow — local clear below is authoritative for the client
      }
      clearSession();
    },
    onSuccess: () => queryClient.invalidateQueries(),
  });
}
