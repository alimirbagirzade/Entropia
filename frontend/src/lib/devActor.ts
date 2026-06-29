// Dev-mode actor selection. Authentication / IdP is a deferred security decision
// (Master §20); until then the dev picks which principal to act as, and the
// API client sends it as the `X-Actor-Id` header. The server still resolves the
// ROLE authoritatively — this only chooses *which* principal you are.

const KEY = "entropia.devActorId";

export function getDevActorId(): string {
  return localStorage.getItem(KEY) ?? "";
}

export function setDevActorId(id: string): void {
  if (id) localStorage.setItem(KEY, id);
  else localStorage.removeItem(KEY);
}
