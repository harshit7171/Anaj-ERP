import { useEffect, useMemo, useState } from "react";

import { emptyExpenseRow, type LiftingExpenseRow } from "./constants";

export default function LiftingExpenseModal({
  open,
  title,
  onQty,
  onWt,
  onAmt,
  rows,
  onClose,
  onSave,
}: {
  open: boolean;
  title: string;
  onQty: string;
  onWt: string;
  onAmt: string;
  rows: LiftingExpenseRow[];
  onClose(): void;
  onSave(rows: LiftingExpenseRow[]): void;
}) {
  const [localRows, setLocalRows] = useState<LiftingExpenseRow[]>(rows);

  useEffect(() => {
    if (!open) return;
    setLocalRows(rows.length ? [...rows, emptyExpenseRow()] : [emptyExpenseRow()]);
  }, [open, rows]);

  const totalExpense = useMemo(
    () =>
      localRows.reduce((sum, row) => sum + (Number(row.amount) || 0), 0).toFixed(2),
    [localRows],
  );

  if (!open) return null;

  function updateRow(index: number, patch: Partial<LiftingExpenseRow>) {
    setLocalRows((prev) => {
      const next = prev.map((row, i) => (i === index ? { ...row, ...patch } : row));
      const row = next[index];
      if (patch.per_pct !== undefined || patch.exp_on !== undefined) {
        const pct = Number(row.per_pct) || 0;
        let base = Number(onAmt) || 0;
        if (row.exp_on === "Nug") base = Number(onQty) || 0;
        if (row.exp_on === "Wt") base = Number(onWt) || 0;
        const amount = ((base * pct) / 100).toFixed(2);
        next[index] = { ...row, amount };
      }
      const last = next[next.length - 1];
      if (last.particulars.trim()) next.push(emptyExpenseRow());
      return next;
    });
  }

  return (
    <div className="lifting-modal-overlay" role="presentation">
      <div className="lifting-expense-modal" role="dialog" aria-label="Lifting expense">
        <header className="lifting-expense-header">
          <strong>{title}</strong>
          <div>
            <button type="button" onClick={() => onSave(localRows.filter((r) => r.particulars.trim()))}>
              Ok
            </button>
            <button type="button" onClick={onClose}>
              Close
            </button>
          </div>
        </header>
        <div className="lifting-expense-summary">
          <span>On Qty: {onQty}</span>
          <span>On Wt.: {onWt}</span>
          <span>On Amt: {onAmt}</span>
          <span>Total Expense: {totalExpense}</span>
        </div>
        <table className="lifting-expense-grid">
          <thead>
            <tr>
              <th>Particulars</th>
              <th>Exp On</th>
              <th>Extra</th>
              <th>Per %</th>
              <th>ROff</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {localRows.map((row, index) => (
              <tr key={`exp-${index}`}>
                <td>
                  <input
                    value={row.particulars}
                    onChange={(event) => updateRow(index, { particulars: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    value={row.exp_on}
                    onChange={(event) => updateRow(index, { exp_on: event.target.value })}
                  >
                    <option value="Nug">Nug</option>
                    <option value="Wt">Wt</option>
                    <option value="Amt">Amt</option>
                  </select>
                </td>
                <td>
                  <select
                    value={row.extra}
                    onChange={(event) => updateRow(index, { extra: event.target.value })}
                  >
                    <option value="N">N</option>
                    <option value="Y">Y</option>
                  </select>
                </td>
                <td>
                  <input
                    value={row.per_pct}
                    onChange={(event) => updateRow(index, { per_pct: event.target.value })}
                  />
                </td>
                <td>
                  <select
                    value={row.r_off}
                    onChange={(event) => updateRow(index, { r_off: event.target.value })}
                  >
                    <option value="N">N</option>
                    <option value="Y">Y</option>
                  </select>
                </td>
                <td>
                  <input
                    value={row.amount}
                    onChange={(event) => updateRow(index, { amount: event.target.value })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
