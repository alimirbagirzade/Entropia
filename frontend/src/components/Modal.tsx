import { useEffect, useRef, type ReactNode } from "react";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

// Shared dialog/drawer chrome (reuses the .modal-overlay/.modal-card pattern
// from app/Layout.tsx's About modal). Escape closes; focus is trapped inside
// while open and restored to the trigger element on close (accessibility.md:
// "Trap focus within modal dialogs. Restore focus to trigger element on close.").
export function Modal({
  open,
  onClose,
  titleId,
  wide = false,
  children,
}: {
  open: boolean;
  onClose: () => void;
  titleId: string;
  wide?: boolean;
  children: ReactNode;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);
  // Track the latest onClose without adding it to the open/close effect's
  // deps — onClose is a fresh closure on every parent render, and including
  // it there would re-run the effect (recapturing triggerRef mid-session) on
  // renders unrelated to an actual open/close transition.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement;
    const card = cardRef.current;
    const first = card?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    first?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !card) return;
      const focusable = Array.from(card.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) return;
      const firstEl = focusable[0];
      const lastEl = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault();
        lastEl.focus();
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault();
        firstEl.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (triggerRef.current instanceof HTMLElement) triggerRef.current.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={onClose}>
      <div
        ref={cardRef}
        className={`modal-card${wide ? " modal-card-wide" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
