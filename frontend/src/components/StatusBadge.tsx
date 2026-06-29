type Tone = "ok" | "warn" | "down" | "neutral";

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const dot = tone === "neutral" ? "" : tone;
  return (
    <span className="badge">
      <span className={`dot ${dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}
