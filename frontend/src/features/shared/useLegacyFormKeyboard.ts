import { useEffect } from "react";

export type LegacyFormShortcutHandlers = {
  onSave?: () => void;
  onView?: () => void;
  onPrint?: () => void;
  onExit: () => void;
  /** When true, F3 triggers onSave (legacy lifting/mandi style). Default: F2 save, F3 view. */
  saveOnF3?: boolean;
  /** When true, F12 also triggers save (TransactionScreen compatibility). */
  saveOnF12?: boolean;
  enabled?: boolean;
};

/**
 * Global F-key layer for Munshi / numpad operators.
 * Default: F2 Save, F3 View (or save if saveOnF3), F4 Cancel/Exit, F7 Print, F12 Save (optional).
 */
function useLegacyFormKeyboard(handlers: LegacyFormShortcutHandlers) {
  const {
    onSave,
    onView,
    onPrint,
    onExit,
    saveOnF3 = false,
    saveOnF12 = false,
    enabled = true,
  } = handlers;

  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
        return;
      }
      if (event.key === "F7" && onPrint) {
        event.preventDefault();
        onPrint();
        return;
      }
      if (saveOnF3 && event.key === "F3" && onSave) {
        event.preventDefault();
        onSave();
        return;
      }
      if (!saveOnF3 && event.key === "F2" && onSave) {
        event.preventDefault();
        onSave();
        return;
      }
      if (!saveOnF3 && event.key === "F3" && onView) {
        event.preventDefault();
        onView();
        return;
      }
      if (saveOnF12 && event.key === "F12" && onSave) {
        event.preventDefault();
        onSave();
        return;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled, onExit, onPrint, onSave, onView, saveOnF3, saveOnF12]);
}

export { useLegacyFormKeyboard };
