// Unique-ish identifiers for entities created against the live stack during a
// run, so repeated CI runs against a persistent (non-reset) Postgres never
// collide on unique constraints (username, email, dataset title, ...).
export function uniqueSuffix(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

export function uniqueUsername(prefix: string): string {
  return `${prefix}_${uniqueSuffix()}`;
}

export function uniqueEmail(prefix: string): string {
  return `${prefix}_${uniqueSuffix()}@e2e.entropia.test`;
}
