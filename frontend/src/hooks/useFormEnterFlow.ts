import { useEffect, type RefObject } from "react";

function focusableInScope(scope: HTMLElement): HTMLElement[] {
  return Array.from(
    scope.querySelectorAll<HTMLElement>(
      "input:not([disabled]):not([type='hidden']), "
        + "select:not([disabled]), textarea:not([disabled]), "
        + "[data-enter-focus='true']:not([disabled])",
    ),
  ).sort((left, right) => {
    const leftOrder = Number(left.dataset.enterOrder ?? Number.MAX_SAFE_INTEGER);
    const rightOrder = Number(right.dataset.enterOrder ?? Number.MAX_SAFE_INTEGER);
    if (leftOrder !== rightOrder) return leftOrder - rightOrder;
    return 0;
  });
}

function useFormEnterFlow(scopeRef: RefObject<HTMLElement | null>, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const scope = scopeRef.current;
    if (!scope) return;

    const moveFocus = (target: HTMLElement, backward: boolean) => {
      const fields = focusableInScope(scope);
      const index = fields.indexOf(target);
      if (index < 0) return;
      if (backward) {
        if (index > 0) fields[index - 1]?.focus();
        return;
      }
      if (index < fields.length - 1) fields[index + 1]?.focus();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target || !scope.contains(target)) return;
      if (target.tagName === "BUTTON") return;

      const backward =
        event.key === "ArrowLeft"
        || (event.key === "Enter" && event.shiftKey)
        || (event.key === "Tab" && event.shiftKey);
      const forward =
        event.key === "ArrowRight"
        || (event.key === "Enter" && !event.shiftKey)
        || (event.key === "Tab" && !event.shiftKey);

      if (!backward && !forward) return;
      if (event.isComposing) return;
      if (target.closest("[data-grid-row]")) return;
      if (target.tagName === "TEXTAREA" && event.key === "Enter" && !event.ctrlKey) return;

      if (target instanceof HTMLSelectElement && forward && event.key === "Enter") {
        event.preventDefault();
        const option = target.options[target.selectedIndex];
        if (option) target.value = option.value;
        moveFocus(target, false);
        return;
      }

      if (event.key === "Tab") return;

      event.preventDefault();
      moveFocus(target, backward);
    };

    scope.addEventListener("keydown", onKeyDown);
    return () => scope.removeEventListener("keydown", onKeyDown);
  }, [enabled, scopeRef]);
}

export { focusableInScope, useFormEnterFlow };
