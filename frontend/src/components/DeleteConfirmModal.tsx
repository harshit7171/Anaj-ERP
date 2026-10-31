import { useState } from "react";

import Button from "./Button";
import Modal from "./Modal";

function DeleteConfirmModal({
  open,
  recordLabel,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  recordLabel: string;
  onCancel(): void;
  onConfirm(): void;
}) {
  const [step, setStep] = useState<1 | 2>(1);

  if (!open) return null;

  function close() {
    setStep(1);
    onCancel();
  }

  return (
    <Modal
      blocking
      tone="danger"
      title={step === 1 ? "Delete record?" : "Final confirmation"}
      onClose={close}
      footer={
        step === 1 ? (
          <>
            <Button type="button" onClick={close}>Cancel</Button>
            <Button type="button" variant="danger" onClick={() => setStep(2)}>
              Yes, continue
            </Button>
          </>
        ) : (
          <>
            <Button type="button" onClick={() => setStep(1)}>Go back</Button>
            <Button type="button" variant="danger" onClick={() => { onConfirm(); setStep(1); }}>
              Confirm delete (Del)
            </Button>
          </>
        )
      }
    >
      {step === 1 ? (
        <p>
          You are about to delete <strong>{recordLabel}</strong>. Mandi records should normally be
          reversed, not erased. Continue only if your auditor approved deletion.
        </p>
      ) : (
        <p className="text-[#dc2626] font-semibold">
          Last step: confirm permanent delete of <strong>{recordLabel}</strong>.
        </p>
      )}
    </Modal>
  );
}

export default DeleteConfirmModal;
