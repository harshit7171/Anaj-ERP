import { useEffect } from "react";

function FormToast({
  message,
  tone = "error",
  onDismiss,
}: {
  message: string;
  tone?: "error" | "warning" | "info";
  onDismiss(): void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, 4500);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  return (
    <div className={`form-toast form-toast-${tone}`} role="status">
      {message}
    </div>
  );
}

export default FormToast;
