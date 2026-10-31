import { useEffect } from "react";
import type { ReactNode } from "react";

import Button from "./Button";

function Modal({
  title,
  children,
  onClose,
  footer,
  blocking = false,
  tone = "default",
  size = "default",
}: {
  title: string;
  children: ReactNode;
  onClose?: () => void;
  footer?: ReactNode;
  blocking?: boolean;
  tone?: "default" | "warning" | "danger";
  size?: "default" | "large" | "transaction";
}) {
  const toneClass =
    tone === "warning"
      ? "border-[#9a6500] bg-[#fff4b8]"
      : tone === "danger"
        ? "border-[#b92a22] bg-[#ffe2dc]"
        : "border-[#37687a] bg-[#c6f2fb]";
  const sizeClass = size === "transaction"
    ? "modal-panel-transaction w-[min(1180px,calc(100vw-2rem))] max-w-none"
    : size === "large"
      ? "modal-panel-large max-w-4xl"
      : "modal-panel-default max-w-lg";

  useEffect(() => {
    if (blocking || !onClose) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [blocking, onClose]);

  return (
    <div
      className="erp-modal-overlay fixed inset-0 z-[1200] flex items-center justify-center p-4"
      onMouseDown={(event) => {
        if (!blocking && onClose && event.target === event.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        className={`erp-modal-panel flex max-h-[calc(100vh-2rem)] w-full flex-col overflow-hidden border ${sizeClass} ${toneClass}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <header className="erp-modal-header flex shrink-0 items-center justify-between border-b px-4 py-3">
          <h2 id="modal-title" className="text-sm font-semibold text-[#17252b]">
            {title}
          </h2>
          {!blocking && onClose && (
            <Button className="erp-modal-close" variant="ghost" onClick={onClose} aria-label="Close">
              ×
            </Button>
          )}
        </header>
        <div className="erp-modal-body min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-3 text-sm text-[#17252b]">
          {children}
        </div>
        {(footer || onClose) && (
          <footer className="erp-modal-footer flex shrink-0 justify-end gap-2 border-t px-4 py-3">
            {footer}
            {!blocking && onClose && !footer && (
              <Button variant="primary" onClick={onClose}>
                OK
              </Button>
            )}
          </footer>
        )}
      </div>
    </div>
  );
}

export default Modal;
