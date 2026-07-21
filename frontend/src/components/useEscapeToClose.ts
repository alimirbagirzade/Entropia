import { useEffect, useRef } from "react";

// Escape-to-dismiss for the anchored popovers (Add menu, Add Package) that are
// NOT the shared <Modal> — they keep the v18 prototype's inline popover chrome,
// so they cannot inherit Modal's key handling. accessibility.md: "Support
// Escape to close modals, dropdowns, and overlays" + "Restore focus to trigger
// element on close".
//
// Presentation-only: no route, query-key, OCC or request behavior is involved.
export function useEscapeToClose(open: boolean, onClose: () => void): void {
  // onClose is a fresh closure each render; keeping it in a ref means the
  // listener effect only re-runs on an actual open/close transition.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onCloseRef.current();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (trigger instanceof HTMLElement) trigger.focus();
    };
  }, [open]);
}
