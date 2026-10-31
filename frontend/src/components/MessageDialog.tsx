import Modal from "./Modal";
import Button from "./Button";

type MessageDialogProps = {
  title?: string;
  message: string;
  tone?: "default" | "warning" | "danger";
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm(): void;
  onCancel?(): void;
};

function MessageDialog({
  title = "Anaj Accounting ERP",
  message,
  tone = "default",
  confirmLabel = "OK",
  cancelLabel,
  onConfirm,
  onCancel,
}: MessageDialogProps) {
  const blocking = !cancelLabel;
  return (
    <Modal
      blocking={blocking}
      onClose={cancelLabel ? onCancel : onConfirm}
      size="default"
      title={title}
      tone={tone}
      footer={(
        <>
          {cancelLabel && onCancel && (
            <Button type="button" onClick={onCancel}>
              {cancelLabel}
            </Button>
          )}
          <Button type="button" variant="primary" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      )}
    >
      <p className="m-0 whitespace-pre-wrap">{message}</p>
    </Modal>
  );
}

export default MessageDialog;
