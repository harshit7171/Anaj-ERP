import { FormEvent, useRef, type ReactNode } from "react";

import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import { useLegacyFormKeyboard, type LegacyFormShortcutHandlers } from "./useLegacyFormKeyboard";

export type LegacyFormContainerProps = {
  title: string;
  entryMode?: "add" | "modify";
  onExit: () => void;
  onSave?: (event?: FormEvent) => void;
  /** F3 when saveOnF3 is false — preview / recalculate / view register */
  onView?: () => void;
  onPrint?: () => void;
  children: ReactNode;
  toolbarExtra?: ReactNode;
  status?: ReactNode;
  /** Shown under title during Phase 1–2 migration */
  migrationNote?: string;
  saveOnF3?: boolean;
  saveOnF12?: boolean;
  className?: string;
};

/**
 * Standard wrapper for grain ERP entry forms: accounts-entry chrome, Enter-as-Tab, F-keys.
 * Use for migrated screens; monolith forms move here incrementally (Phase 2).
 */
function LegacyFormContainer({
  title,
  entryMode = "add",
  onExit,
  onSave,
  onView,
  onPrint,
  children,
  toolbarExtra,
  status,
  migrationNote,
  saveOnF3 = false,
  saveOnF12 = false,
  className = "",
}: LegacyFormContainerProps) {
  const formRef = useRef<HTMLFormElement>(null);
  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  const keyboard: LegacyFormShortcutHandlers = {
    onExit,
    onSave: onSave ? () => onSave() : undefined,
    onView,
    onPrint,
    saveOnF3,
    saveOnF12,
  };
  useLegacyFormKeyboard(keyboard);

  const saveLabel = saveOnF3 ? "Save (F3)" : "Save (F2)";
  const viewLabel = saveOnF3 ? undefined : "View (F3)";

  return (
    <form
      ref={formRef}
      className={`accounts-entry-screen legacy-form-container ${className}`.trim()}
      data-entry-mode={entryMode}
      data-grid-scope
      data-mandi-form
      onSubmit={(event) => {
        event.preventDefault();
        onSave?.(event);
      }}
    >
      <header className="accounts-entry-title">{title}</header>
      {migrationNote && <p className="accounts-entry-status">{migrationNote}</p>}

      <div className="accounts-entry-toolbar">
        {onSave && (
          <button type="submit" className="accent-btn">
            {saveLabel}
          </button>
        )}
        {viewLabel && onView && (
          <button type="button" onClick={() => onView()}>
            {viewLabel}
          </button>
        )}
        {onPrint && (
          <button type="button" onClick={() => onPrint()}>
            Print (F7)
          </button>
        )}
        {toolbarExtra}
        <button type="button" onClick={onExit}>
          Cancel (F4)
        </button>
      </div>

      <div className="legacy-form-body">{children}</div>
      {status}
    </form>
  );
}

export default LegacyFormContainer;
