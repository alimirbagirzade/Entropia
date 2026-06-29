# Entropia V18 — Frontend

React 18 · TypeScript · Vite · TanStack Query · React Hook Form. The backend is
the single source of truth (Module 20 §9): this app renders server projections
and reacts to SSE refresh signals; it never computes domain state.

## Develop

```bash
npm install
cp .env.example .env            # set VITE_API_BASE_URL if not default
npm run dev                     # http://localhost:5173
```

The API must be reachable at `VITE_API_BASE_URL` (run `docker compose up -d` or
`make backend-dev` from the repo root).

## Scripts

| Command            | Purpose                                  |
| ------------------ | ---------------------------------------- |
| `npm run dev`      | Vite dev server with HMR                 |
| `npm run build`    | Type-check + production build to `dist/` |
| `npm run preview`  | Preview the production build             |
| `npm run lint`     | ESLint (flat config)                     |
| `npm run typecheck`| `tsc` no-emit type check                 |
| `npm test`         | Vitest unit tests                        |

## Structure

```
src/
  app/         Layout (shell), nav config (all 22 screens)
  lib/         apiClient · queryClient · sse · hooks · types
  components/  Loading · EmptyState · ErrorState · ErrorBoundary · StatusBadge
  pages/       Mainboard (live status) · Placeholder · NotFound
  styles/      global theme (dark/light, reduced-motion, focus-visible)
```
