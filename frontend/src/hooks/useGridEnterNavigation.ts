import { useCallback } from "react";
import type { KeyboardEvent } from "react";

function focusableInRow(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      "input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [data-grid-focus='true']:not([disabled])",
    ),
  );
}

function focusFirstFieldInAppendedRow(
  row: HTMLElement,
  scope: HTMLElement,
  attempt = 0,
): void {
  const section = row.dataset.section;
  const selector = section
    ? `[data-grid-row][data-section="${CSS.escape(section)}"]`
    : "[data-grid-row]";
  const rows = scope.querySelectorAll<HTMLElement>(selector);
  const candidate = rows[rows.length - 1];
  if (candidate && candidate !== row) {
    focusableInRow(candidate)[0]?.focus();
    candidate.scrollIntoView({ block: "nearest" });
    return;
  }
  if (attempt < 5) {
    requestAnimationFrame(() => focusFirstFieldInAppendedRow(row, scope, attempt + 1));
  }
}

type RowCompletion = (row: HTMLElement) => boolean | void;
type ValidatableControl = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

function isValidatableControl(field: HTMLElement): field is ValidatableControl {
  return field instanceof HTMLInputElement
    || field instanceof HTMLSelectElement
    || field instanceof HTMLTextAreaElement;
}

function useGridEnterNavigation(onRowComplete?: RowCompletion) {
  return useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const row = target.closest<HTMLElement>("[data-grid-row]");
      if (!row) return;

      const isEnter = event.key === "Enter" && !event.nativeEvent.isComposing;
      const isRight = event.key === "ArrowRight";
      const isLeft = event.key === "ArrowLeft";
      if (!isEnter && !isRight && !isLeft) return;

      const fields = focusableInRow(row);
      const index = fields.indexOf(target);
      const backward = isLeft || (isEnter && event.shiftKey);
      const forward = isRight || (isEnter && !event.shiftKey);

      if (backward) {
        event.preventDefault();
        event.stopPropagation();
        if (index > 0) fields[index - 1]?.focus();
        return;
      }
      if (!forward) return;

      if (index >= 0 && index < fields.length - 1) {
        event.preventDefault();
        event.stopPropagation();
        fields[index + 1]?.focus();
        return;
      }
      if (!isEnter) return;

      event.preventDefault();
      event.stopPropagation();
      const invalid = fields.filter(isValidatableControl).find((field) => !field.checkValidity());
      if (invalid) {
        invalid.reportValidity();
        invalid.focus();
        return;
      }
      if (onRowComplete?.(row) === false) return;
      const scope = row.closest<HTMLElement>("[data-grid-scope], form") ?? document.body;
      requestAnimationFrame(() => focusFirstFieldInAppendedRow(row, scope));
    },
    [onRowComplete],
  );
}

export { focusableInRow, useGridEnterNavigation };
