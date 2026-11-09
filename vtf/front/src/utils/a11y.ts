import type { KeyboardEvent } from "react";

/** Invoke `action` when the user activates a faux button with Enter or Space. */
export function activateOnKeyboard(
  event: KeyboardEvent<HTMLElement>,
  action: () => void,
): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}
