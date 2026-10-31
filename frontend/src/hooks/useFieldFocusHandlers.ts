import { useEffect, type RefObject } from "react";

/** Select-all on numeric inputs; expand dropdown size on focus. */
function useFieldFocusHandlers(scopeRef: RefObject<HTMLElement | null>, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const scope = scopeRef.current;
    if (!scope) return;

    const onFocusIn = (event: FocusEvent) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement)) {
        if (target instanceof HTMLSelectElement) {
          target.size = Math.min(target.options.length, 6);
        }
        return;
      }
      if (
        target.type === "number"
        || target.inputMode === "decimal"
        || target.inputMode === "numeric"
        || target.classList.contains("mandi-numeric")
      ) {
        requestAnimationFrame(() => target.select());
      }
    };

    const onFocusOut = (event: FocusEvent) => {
      const target = event.target;
      if (target instanceof HTMLSelectElement) {
        target.size = 1;
      }
    };

    scope.addEventListener("focusin", onFocusIn);
    scope.addEventListener("focusout", onFocusOut);
    return () => {
      scope.removeEventListener("focusin", onFocusIn);
      scope.removeEventListener("focusout", onFocusOut);
    };
  }, [enabled, scopeRef]);
}

export default useFieldFocusHandlers;
