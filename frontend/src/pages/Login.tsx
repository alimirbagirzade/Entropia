import { useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/lib/apiClient";
import { useLogin, useSignup } from "@/lib/auth";
import { useAuthMode } from "@/lib/authMode";
import { useMeta } from "@/lib/hooks";

type Mode = "login" | "signup";

interface FormValues {
  username: string;
  password: string;
  display_name: string;
  email: string;
}

// Standalone auth page (no app shell). Login and Signup share one form; Signup
// exposes the optional display-name/email fields. Errors surface the backend's
// canonical envelope verbatim — the client never invents auth messages.
export function Login() {
  const [mode, setMode] = useState<Mode>("login");
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const signup = useSignup();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ defaultValues: { username: "", password: "", display_name: "", email: "" } });

  const active = mode === "login" ? login : signup;
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const done = () => navigate(from, { replace: true });

  // The login route follows the SERVER's auth mode too. /meta is fetched here
  // because this page renders outside the app shell, so on a direct visit to
  // /login nothing else would populate the store.
  useMeta();
  const authMode = useAuthMode();

  function onSubmit(values: FormValues) {
    if (mode === "login") {
      login.mutate({ username: values.username, password: values.password }, { onSuccess: done });
    } else {
      signup.mutate(
        {
          username: values.username,
          password: values.password,
          display_name: values.display_name.trim() || undefined,
          email: values.email.trim() || undefined,
        },
        { onSuccess: done },
      );
    }
  }

  const err = active.error;
  const errMsg =
    err instanceof ApiError
      ? `${err.code}: ${err.message}`
      : err instanceof Error
        ? err.message
        : null;

  function switchMode(next: Mode) {
    if (next !== mode) {
      login.reset();
      signup.reset();
      setMode(next);
    }
  }

  // Dev mode: the API resolves identity from X-Actor-Id and ignores session
  // tokens outright, so a working-looking form here would mint a credential the
  // backend discards — the exact "login 200 -> protected 401" trap. Explain the
  // mode and route back to the app, where the “act as” control does the real work.
  if (authMode === "dev") {
    return (
      <div className="auth-viewport">
        <div className="card auth-card">
          <div className="brand" style={{ marginBottom: 18 }}>
            <span className="logo" aria-hidden="true" />
            <span>ENTROPIA</span>
          </div>
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Local development mode</h2>
          <p style={{ color: "var(--text-dim)" }}>
            This server runs with <code>AUTH_MODE=dev</code>. Identity comes from the{" "}
            <strong>“act as”</strong> field in the top bar (sent as <code>X-Actor-Id</code>) and is
            resolved server-side — Sign Up and Log In are inactive because the API ignores session
            tokens in this mode.
          </p>
          <p style={{ color: "var(--text-dim)" }}>
            For real Sign Up / Log In, start the stack with <code>AUTH_MODE=session</code>.
          </p>
          <button type="button" className="btn btn-primary auth-submit" onClick={() => navigate("/")}>
            Back to Entropia
          </button>
        </div>
      </div>
    );
  }

  // Mode not known yet (/meta in flight): a neutral placeholder, so the form
  // never flashes on a dev-mode server before /meta answers.
  if (authMode === null) {
    return (
      <div className="auth-viewport">
        <div className="card auth-card" aria-busy="true">
          <div className="brand" style={{ marginBottom: 18 }}>
            <span className="logo" aria-hidden="true" />
            <span>ENTROPIA</span>
          </div>
          <p style={{ color: "var(--text-dim)" }}>Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-viewport">
      <div className="card auth-card">
        <div className="brand" style={{ marginBottom: 18 }}>
          <span className="logo" aria-hidden="true" />
          <span>ENTROPIA</span>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={`auth-tab${mode === "login" ? " active" : ""}`}
            onClick={() => switchMode("login")}
          >
            Log in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signup"}
            className={`auth-tab${mode === "signup" ? " active" : ""}`}
            onClick={() => switchMode("signup")}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <label className="auth-field">
            <span>Username</span>
            <input
              className="auth-input"
              autoComplete="username"
              autoFocus
              aria-invalid={errors.username ? true : undefined}
              {...register("username", { required: "Username is required" })}
            />
            {errors.username ? <em className="auth-hint">{errors.username.message}</em> : null}
          </label>

          <label className="auth-field">
            <span>Password</span>
            <input
              className="auth-input"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              aria-invalid={errors.password ? true : undefined}
              {...register("password", { required: "Password is required" })}
            />
            {errors.password ? <em className="auth-hint">{errors.password.message}</em> : null}
          </label>

          {mode === "signup" ? (
            <>
              <label className="auth-field">
                <span>
                  Display name <span className="auth-optional">optional</span>
                </span>
                <input className="auth-input" autoComplete="name" {...register("display_name")} />
              </label>
              <label className="auth-field">
                <span>
                  Email <span className="auth-optional">optional</span>
                </span>
                <input className="auth-input" type="email" autoComplete="email" {...register("email")} />
              </label>
            </>
          ) : null}

          {errMsg ? (
            <p className="auth-error" role="alert">
              {errMsg}
            </p>
          ) : null}

          <button type="submit" className="btn btn-primary auth-submit" disabled={active.isPending}>
            {active.isPending ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
