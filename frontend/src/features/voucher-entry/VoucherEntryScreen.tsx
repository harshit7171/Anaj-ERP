import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import {
  emptyVoucherLine,
  isoToday,
  parseVoucherLines,
  weekdayLabel,
  withTrailingBlankLine,
  type VoucherLine,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type VoucherApi = {
  get_voucher_entry?(args: Record<string, string>): Promise<ApiResult & { voucher_entry?: Record<string, unknown> }>;
  save_voucher_entry?(payload: Record<string, unknown>): Promise<ApiResult & { voucher_entry?: Record<string, unknown> }>;
  lookup_voucher_entry_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_voucher_entry_banks?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  voucher_entry_account_balance?(account_id: string, as_of_date: string): Promise<ApiResult & { balance_paise?: number }>;
  voucher_entry_cash_in_hand?(as_of_date: string): Promise<ApiResult & Record<string, unknown>>;
  voucher_entry_line_hints?(account_id: string): Promise<ApiResult & { hints?: Record<string, string> }>;
  next_voucher_entry_number?(voucher_type?: string): Promise<ApiResult & { voucher_number?: string }>;
};

function bridge(): VoucherApi | undefined {
  return window.pywebview?.api as unknown as VoucherApi | undefined;
}

export default function VoucherEntryScreen({ mode, onExit }: { mode: "add" | "modify"; onExit(): void }) {
  const title = mode === "add" ? "Voucher Entry" : "Voucher Entry Modify";
  const formRef = useRef<HTMLFormElement>(null);

  const [voucherId, setVoucherId] = useState("");
  const [voucherNumber, setVoucherNumber] = useState("");
  const [voucherDate, setVoucherDate] = useState(isoToday());
  const [voucherType, setVoucherType] = useState("Receipt");
  const [paymentMode, setPaymentMode] = useState("Cash");
  const [headerAccountId, setHeaderAccountId] = useState("");
  const [headerAccountName, setHeaderAccountName] = useState("");
  const [userName, setUserName] = useState("USER");
  const [lines, setLines] = useState<VoucherLine[]>([emptyVoucherLine()]);
  const [cashInHand, setCashInHand] = useState("0.00");
  const [picker, setPicker] = useState<{ kind: "account" | "bank"; lineIndex: number; rows: Record<string, unknown>[] } | null>(
    null,
  );
  const [bulkCheque, setBulkCheque] = useState("");
  const [bulkParticulars, setBulkParticulars] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const weekday = useMemo(() => weekdayLabel(voucherDate), [voucherDate]);

  const totals = useMemo(() => {
    let debit = 0;
    let credit = 0;
    for (const line of lines) {
      const amount = Number(line.amount) || 0;
      const discount = Number(line.discount) || 0;
      const net = amount - discount;
      if (net <= 0) continue;
      if (voucherType === "Receipt") credit += net;
      else if (voucherType === "Payment") debit += net;
      else {
        debit += net;
        credit += net;
      }
    }
    if (voucherType === "Receipt") debit = credit;
    if (voucherType === "Payment") credit = debit;
    return { debit, credit, diff: Math.abs(debit - credit) };
  }, [lines, voucherType]);

  useEffect(() => {
    void bridge()?.voucher_entry_cash_in_hand?.(voucherDate).then((response) => {
      if (!response?.ok) return;
      const paise = Number(response.cash_in_hand_paise ?? 0);
      setCashInHand((paise / 100).toFixed(2));
      if (paymentMode === "Cash" && !headerAccountId && response.cash_account_id) {
        setHeaderAccountId(String(response.cash_account_id));
        setHeaderAccountName(String(response.cash_account_name ?? ""));
      }
    });
  }, [voucherDate, paymentMode, headerAccountId]);

  useEffect(() => {
    if (mode !== "add") return;
    void bridge()?.next_voucher_entry_number?.(voucherType).then((response) => {
      if (response?.ok && response.voucher_number) setVoucherNumber(response.voucher_number);
    });
  }, [mode, voucherType]);

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => withTrailingBlankLine(prev));
    return false;
  });

  function applyRecord(record: Record<string, unknown>) {
    setVoucherId(String(record.voucher_id ?? ""));
    setVoucherNumber(String(record.voucher_number ?? ""));
    setVoucherDate(String(record.voucher_date ?? isoToday()));
    setVoucherType(String(record.voucher_type ?? "Receipt"));
    setPaymentMode(String(record.payment_mode ?? "Cash"));
    setHeaderAccountId(String(record.header_account_id ?? ""));
    setHeaderAccountName(String(record.header_account_name ?? ""));
    setUserName(String(record.user_name ?? "USER"));
    setLines(parseVoucherLines(record.lines));
    setStatus("Voucher loaded.");
    setError("");
  }

  async function runFind() {
    const response = await bridge()?.get_voucher_entry?.({
      voucher_number: voucherNumber.trim(),
      voucher_date: voucherDate,
      voucher_type: voucherType,
    });
    if (!response?.ok || !response.voucher_entry) {
      setError(response?.error ?? "Voucher not found.");
      return;
    }
    applyRecord(response.voucher_entry);
  }

  async function openPicker(kind: "account" | "bank", lineIndex: number, query = "") {
    const api = bridge();
    if (!api) return;
    const fn = kind === "bank" ? api.lookup_voucher_entry_banks : api.lookup_voucher_entry_accounts;
    const q = kind === "bank" ? query || headerAccountName : query || lines[lineIndex]?.account_name;
    const response = await fn?.(q);
    if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
  }

  async function applyAccount(lineIndex: number, row: Record<string, unknown>) {
    const accountId = String(row.account_id ?? "");
    const accountName = String(row.account_name ?? row.bank_name ?? row.name ?? "");
    if (lineIndex < 0) {
      setHeaderAccountId(accountId);
      setHeaderAccountName(accountName);
      setPicker(null);
      return;
    }
    const hints = await bridge()?.voucher_entry_line_hints?.(accountId);
    const balance = await bridge()?.voucher_entry_account_balance?.(accountId, voucherDate);
    setLines((prev) =>
      withTrailingBlankLine(
        prev.map((line, index) =>
          index === lineIndex
            ? {
                ...line,
                account_id: accountId,
                account_name: accountName,
                balance:
                  balance?.ok && balance.balance_paise !== undefined
                    ? (Number(balance.balance_paise) / 100).toFixed(2)
                    : line.balance,
                narration: hints?.hints?.narration ?? line.narration,
                due_date: hints?.hints?.due_date ?? line.due_date,
                cheque_no: hints?.hints?.cheque_no ?? line.cheque_no,
              }
            : line,
        ),
      ),
    );
    setPicker(null);
  }

  function updateLine(index: number, patch: Partial<VoucherLine>) {
    setLines((prev) => withTrailingBlankLine(prev.map((line, i) => (i === index ? { ...line, ...patch } : line))));
  }

  function applyBulkCheque() {
    if (!bulkCheque.trim()) return;
    setLines((prev) => prev.map((line) => ({ ...line, cheque_no: bulkCheque.trim() })));
    setStatus("Cheque number applied to all lines.");
  }

  function applyBulkParticulars() {
    if (!bulkParticulars.trim()) return;
    setLines((prev) => prev.map((line) => ({ ...line, narration: bulkParticulars.trim() })));
    setStatus("Particulars applied to all lines.");
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const payload: Record<string, unknown> = {
      voucher_id: voucherId || undefined,
      voucher_number: voucherNumber,
      voucher_date: voucherDate,
      voucher_type: voucherType,
      payment_mode: paymentMode,
      header_account_id: headerAccountId,
      header_account_name: headerAccountName,
      user_name: userName,
      lines: lines.filter((line) => line.account_id && Number(line.amount) > 0),
    };
    const response = await bridge()?.save_voucher_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.voucher_entry) applyRecord(response.voucher_entry);
    setStatus("Data has been Successfully Saved");
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        void save();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
      if (event.key === "F5" && mode === "modify") {
        event.preventDefault();
        void runFind();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <form ref={formRef} className="accounts-entry-screen voucher-entry-screen" onSubmit={(event) => void save(event)}>
        <header className="accounts-entry-title">{title}</header>
        <div className="accounts-entry-toolbar">
          {mode === "modify" && (
            <button type="button" onClick={() => void runFind()}>
              Find (F5)
            </button>
          )}
          <button type="submit">Save (F3)</button>
          <button type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <div className="voucher-entry-header">
          <label>
            Voucher Type
            <select value={voucherType} onChange={(event) => setVoucherType(event.target.value)}>
              <option>Receipt</option>
              <option>Payment</option>
              <option>Contra</option>
              <option>Journal</option>
            </select>
          </label>
          <label>
            Voucher Date
            <input type="date" value={voucherDate} onChange={(event) => setVoucherDate(event.target.value)} />
            <span className="voucher-weekday">{weekday}</span>
          </label>
          <label>
            Type
            <select
              value={paymentMode}
              onChange={(event) => {
                setPaymentMode(event.target.value);
                if (event.target.value === "Cash") setHeaderAccountName("");
              }}
            >
              <option>Cash</option>
              <option>Bank</option>
            </select>
          </label>
          <label>
            VCode
            <input readOnly value={voucherNumber} onChange={(event) => setVoucherNumber(event.target.value)} />
          </label>
          <label>
            User Name
            <input value={userName} onChange={(event) => setUserName(event.target.value)} />
          </label>
          <label className="span-2">
            Bank Name
            <input
              className="picker-field"
              readOnly={paymentMode === "Cash"}
              value={paymentMode === "Cash" ? headerAccountName : headerAccountName}
              onChange={(event) => setHeaderAccountName(event.target.value)}
              onDoubleClick={() => paymentMode === "Bank" && void openPicker("bank", -1)}
            />
          </label>
          <div className="voucher-cash-in-hand">
            Cash In Hand: <strong>{cashInHand}</strong>
          </div>
          <div className="voucher-totals">
            <span>Total Debit: {totals.debit.toFixed(2)}</span>
            <span>Total Credit: {totals.credit.toFixed(2)}</span>
            <span>Difference: {totals.diff.toFixed(2)}</span>
          </div>
        </div>

        <div className="voucher-grid-tools">
          <button type="button" onClick={applyBulkCheque}>
            Set Cheque No
          </button>
          <input placeholder="Cheque no." value={bulkCheque} onChange={(event) => setBulkCheque(event.target.value)} />
          <button type="button" onClick={applyBulkParticulars}>
            Set Particulars
          </button>
          <input
            placeholder="Particulars"
            value={bulkParticulars}
            onChange={(event) => setBulkParticulars(event.target.value)}
          />
        </div>

        <table className="accounts-entry-grid" onKeyDown={handleGridEnter}>
          <thead>
            <tr>
              <th>#</th>
              <th>Account Name</th>
              <th>Balance</th>
              <th>Narration</th>
              <th>Amount</th>
              <th>Discount</th>
              <th>Due Date</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={`vline-${index}`}>
                <td>{index + 1}</td>
                <td>
                  <input
                    className="picker-field"
                    value={line.account_name}
                    onChange={(event) => updateLine(index, { account_name: event.target.value })}
                    onDoubleClick={() => void openPicker("account", index, line.account_name)}
                  />
                </td>
                <td>
                  <input readOnly value={line.balance} />
                </td>
                <td>
                  <input value={line.narration} onChange={(event) => updateLine(index, { narration: event.target.value })} />
                </td>
                <td>
                  <input
                    inputMode="decimal"
                    value={line.amount}
                    onChange={(event) => updateLine(index, { amount: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    inputMode="decimal"
                    value={line.discount}
                    onChange={(event) => updateLine(index, { discount: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    type="date"
                    value={line.due_date}
                    onChange={(event) => updateLine(index, { due_date: event.target.value })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {status && <p className="accounts-entry-status">{status}</p>}
        {error && <p className="accounts-entry-error">{error}</p>}
      </form>

      {picker && (
        <div className="accounts-picker-overlay" role="dialog">
          <div className="accounts-picker-panel">
            <header>Select {picker.kind === "bank" ? "bank" : "account"}</header>
            <ul>
              {picker.rows.map((row) => (
                <li key={String(row.account_id)}>
                  <button type="button" onClick={() => void applyAccount(picker.lineIndex, row)}>
                    {String(row.account_name ?? row.bank_name ?? row.name)}
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" onClick={() => setPicker(null)}>
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
