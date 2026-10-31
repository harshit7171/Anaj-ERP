import type { ReactNode } from "react";

import Modal from "./Modal";

function TransactionWindowModal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose(): void;
}) {
  return (
    <Modal footer={<></>} onClose={onClose} size="transaction" title={title}>
      <div className="transaction-modal-body min-h-[420px]">{children}</div>
    </Modal>
  );
}

export default TransactionWindowModal;
