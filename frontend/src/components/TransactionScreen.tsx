import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import Button from "./Button";
import DeleteConfirmModal from "./DeleteConfirmModal";
import useFieldFocusHandlers from "../hooks/useFieldFocusHandlers";
import { useFormEnterFlow } from "../hooks/useFormEnterFlow";

function TransactionScreen({
  title,
  header,
  grid,
  sidebar,
  footerMessage,
  onSave,
  onPrint,
  onExit,
  onSubmit,
  onDelete,
  entryMode = "add",
  modifySearch,
  auditTrail,
}: {
  title: string;
  header: ReactNode;
  grid: ReactNode;
  sidebar?: ReactNode;
  footerMessage?: ReactNode;
  onSave?(event: FormEvent): void;
  onPrint?(): void;
  onExit(): void;
  onSubmit?(event: FormEvent): void;
  onDelete?(): void;
  entryMode?: "add" | "modify";
  modifySearch?: ReactNode;
  auditTrail?: ReactNode;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  useEffect(() => {
    if (entryMode !== "add") return;
    const scope = formRef.current;
    if (!scope) return;
    window.requestAnimationFrame(() => {
      const first = scope.querySelector<HTMLElement>(
        "input:not([disabled]):not([readonly]):not([type='hidden']), "
          + "select:not([disabled]), textarea:not([disabled])",
      );
      first?.focus();
    });
  }, [entryMode, title]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F12") {
        event.preventDefault();
        formRef.current?.requestSubmit();
      }
      if (event.key === "F7" && onPrint) {
        event.preventDefault();
        onPrint();
      }
      if (event.key === "Delete" && entryMode === "modify" && onDelete) {
        const target = event.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [entryMode, onDelete, onPrint]);

  return (
    <>
      <form
        ref={formRef}
        className="transaction-screen mandi-zero-scroll"
        data-entry-mode={entryMode}
        data-grid-scope
        data-mandi-form
        onSubmit={onSubmit ?? onSave}
      >
        <header className="transaction-header">
          <div className="transaction-title">{title}</div>
          {modifySearch}
          <div className="transaction-header-grid">{header}</div>
        </header>
        <div className={`transaction-body ${sidebar ? "has-sidebar" : ""}`}>
          <section className="transaction-grid-panel">{grid}</section>
          {sidebar && <aside className="transaction-summary-panel">{sidebar}</aside>}
        </div>
        {auditTrail && <section className="transaction-audit-panel">{auditTrail}</section>}
        <footer className="transaction-footer">
          <div className="transaction-footer-message">{footerMessage}</div>
          <div className="transaction-footer-actions">
            {onSave && (
              <Button className="btn-tactile-save" type="submit" variant="save">
                Save (F12)
              </Button>
            )}
            {onPrint && (
              <Button className="btn-tactile-print" type="button" variant="print" onClick={onPrint}>
                Print (F7)
              </Button>
            )}
            {entryMode === "modify" && onDelete && (
              <Button
                className="btn-tactile-delete"
                type="button"
                variant="danger"
                onClick={() => setDeleteOpen(true)}
              >
                Delete (Del)
              </Button>
            )}
            <Button type="button" onClick={onExit}>Exit</Button>
          </div>
        </footer>
      </form>
      {onDelete && (
        <DeleteConfirmModal
          open={deleteOpen}
          recordLabel={title}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => {
            setDeleteOpen(false);
            onDelete();
          }}
        />
      )}
    </>
  );
}

export function InlineField({
  label,
  children,
  required = false,
}: {
  label: string;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <label className="inline-flex min-h-8 min-w-0 items-center gap-2 text-xs font-semibold text-[#17252b]">
      <span className="shrink-0">
        {label}
        {required && <span aria-hidden className="mandi-required">*</span>}
      </span>
      <span className="min-w-0 flex-1">{children}</span>
    </label>
  );
}

export default TransactionScreen;
