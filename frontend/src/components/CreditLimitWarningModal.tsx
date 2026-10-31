import { useState } from "react";

import type { CreditEvaluation } from "../api/types";
import Button from "./Button";
import Modal from "./Modal";

function formatRupees(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}

function CreditLimitWarningModal({
  evaluation,
  onCancel,
  onProceed,
}: {
  evaluation: CreditEvaluation;
  onCancel(): void;
  onProceed(managerPin: string): void;
}) {
  const [pin, setPin] = useState("");

  return (
    <Modal
      blocking
      tone="warning"
      title="⚠️ Credit Limit Breached!"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="danger" onClick={() => onProceed(pin)}>
            Proceed with Manager PIN
          </Button>
        </>
      }
    >
      <p>
        This farmer has an active borrowing limit of{" "}
        <strong>{formatRupees(evaluation.credit_limit_paise)}</strong>.
        Current transaction will push them over their limit by{" "}
        <strong>{formatRupees(evaluation.overage_paise)}</strong>.
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div><dt className="text-[#37687a]">Exposure (ledger + advances + interest)</dt><dd>{formatRupees(evaluation.current_balance_paise)}</dd></div>
        <div><dt className="text-[#37687a]">New Amount</dt><dd>{formatRupees(evaluation.additional_debit_paise)}</dd></div>
        <div><dt className="text-[#37687a]">Projected Balance</dt><dd>{formatRupees(evaluation.projected_balance_paise)}</dd></div>
        <div><dt className="text-[#37687a]">Available Credit</dt><dd>{evaluation.available_credit_paise == null ? "Not set" : formatRupees(evaluation.available_credit_paise)}</dd></div>
      </dl>
      <label className="mt-3 block text-xs">
        Manager / Admin PIN
        <input
          className="mt-1 w-full"
          type="password"
          autoComplete="off"
          value={pin}
          onChange={(event) => setPin(event.target.value)}
        />
      </label>
    </Modal>
  );
}

export default CreditLimitWarningModal;
