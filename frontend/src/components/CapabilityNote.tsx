import type { CapabilityNote } from "@/components/capabilityDisclosure";

/** Renders the note a select points at via `aria-describedby`; `null` when there is none. */
export function CapabilityNoteText({ note, id }: { note: CapabilityNote; id: string }) {
  if (note.kind === "none") return null;
  if (note.kind === "saved_inert") {
    return (
      <p className="sd-capability-note" id={id}>
        <strong>Saved but inert here:</strong> {note.option.label} executes nothing in this
        configuration — {note.reason} Ready Check does not block the run.
      </p>
    );
  }
  return (
    <p className="sd-capability-note" id={id}>
      {note.kind === "saved_blocked" ? (
        <>
          <strong>Not available in this build:</strong> {note.option.label} is saved but will not
          run — Ready Check blocks it. {note.option.dependency}
        </>
      ) : (
        <>
          <strong>Not available in this build:</strong>{" "}
          {note.options.map((entry) => `${entry.label} — ${entry.dependency}`).join(" ")}
        </>
      )}
    </p>
  );
}
