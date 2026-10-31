import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import {
  EXPENSE_DR_CR,
  EXPENSE_NATURES,
  EXPENSE_R_OFF,
  EXPENSES_ON,
  emptyExpenseLine,
  type ExpenseLine,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type ExpenseApi = {
  list_expense_masters?(): Promise<
    ApiResult & { expense_masters?: Record<string, unknown>[] }
  >;
  get_expense_master?(id: string): Promise<
    ApiResult & { expense_master?: Record<string, unknown> }
  >;
  save_expense_master?(payload: Record<string, unknown>): Promise<ApiResult>;
  delete_expense_master?(id: string): Promise<ApiResult>;
  find_accounts?(query?: string): Promise<
    ApiResult & { rows?: Record<string, unknown>[] }
  >;
};

function api(): ExpenseApi | undefined {
  return window.pywebview?.api as unknown as ExpenseApi | undefined;
}

function parseLines(raw: unknown): ExpenseLine[] {
  if (!Array.isArray(raw) || !raw.length) {
    return [emptyExpenseLine()];
  }
  return raw.map((row) => {
    const item = row as Record<string, unknown>;
    return {
      expense_name: String(item.expense_name ?? ""),
      nature: EXPENSE_NATURES.includes(item.nature as never)
        ? (item.nature as ExpenseLine["nature"])
        : "Dami",
      expenses_on: EXPENSES_ON.includes(item.expenses_on as never)
        ? (item.expenses_on as ExpenseLine["expenses_on"])
        : "Amt",
      rate: String(item.rate ?? "0"),
      stage: String(item.stage ?? "1"),
      account_name: String(item.account_name ?? ""),
      dr_cr: EXPENSE_DR_CR.includes(item.dr_cr as never)
        ? (item.dr_cr as ExpenseLine["dr_cr"])
        : "D",
      r_off: EXPENSE_R_OFF.includes(item.r_off as never)
        ? (item.r_off as ExpenseLine["r_off"])
        : "N",
      rcm_applicable: String(item.rcm_applicable ?? "No"),
      blocked_itc: String(item.blocked_itc ?? "No"),
    };
  });
}

function withTrailingBlank(lines: ExpenseLine[]): ExpenseLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.expense_name.trim()) {
    copy.push(emptyExpenseLine());
  } else if (!copy.length) {
    copy.push(emptyExpenseLine());
  }
  return copy;
}

export default function ExpenseMasterScreen({ onExit }: { onExit(): void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const [masterId, setMasterId] = useState("");
  const [masterName, setMasterName] = useState("");
  const [mandiName, setMandiName] = useState("");
  const [lines, setLines] = useState<ExpenseLine[]>([emptyExpenseLine()]);
  const [accountNames, setAccountNames] = useState<string[]>([]);

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findRows, setFindRows] = useState<Record<string, unknown>[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  const appendLine = () => {
    setLines((prev) => withTrailingBlank(prev));
    return true;
  };

  const handleGridEnter = useGridEnterNavigation((row) => {
    const inputs = row.querySelectorAll("input");
    const nameInput = inputs[0] as HTMLInputElement | undefined;
    if (nameInput?.value.trim()) {
      appendLine();
    }
    return false;
  });

  useEffect(() => {
    void api()?.find_accounts?.("").then((response) => {
      if (!response?.ok || !response.rows) return;
      const names = response.rows
        .map((row) => String(row.name ?? row.account_name ?? "").trim())
        .filter(Boolean);
      setAccountNames([...new Set(names)].sort((a, b) => a.localeCompare(b)));
    });
  }, []);

  async function refreshFindList(query: string) {
    const response = await api()?.list_expense_masters?.();
    if (!response?.ok) {
      setFindRows([]);
      return;
    }
    const q = query.trim().toLowerCase();
    const rows = (response.expense_masters ?? []).filter((row) => {
      if (!q) return true;
      const hay = [row.name, row.mandi_name, row.expense_master_id]
        .map((v) => String(v ?? "").toLowerCase())
        .join(" ");
      return hay.includes(q);
    });
    setFindRows(rows);
  }

  function applyRecord(row: Record<string, unknown>) {
    setMasterId(String(row.expense_master_id ?? ""));
    setMasterName(String(row.name ?? ""));
    setMandiName(String(row.mandi_name ?? ""));
    setLines(withTrailingBlank(parseLines(row.lines)));
    setFindOpen(false);
    setStatus("Expense master loaded.");
    setError("");
  }

  async function runFind(searchText?: string) {
    const bridge = api();
    if (!bridge) {
      setError("Desktop API is not available.");
      return;
    }
    const query = (searchText ?? masterName ?? findQuery).trim();
    if (query && !findOpen) {
      const detail = await bridge.get_expense_master?.(query);
      if (detail?.ok && detail.expense_master) {
        applyRecord(detail.expense_master);
        return;
      }
    }
    await refreshFindList(query);
    setFindQuery(query);
    setFindOpen(true);
  }

  function updateLine(index: number, patch: Partial<ExpenseLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => (i === index ? { ...line, ...patch } : line));
      return withTrailingBlank(next);
    });
  }

  function linesForSave(): Record<string, unknown>[] {
    return lines
      .filter((line) => line.expense_name.trim())
      .map((line) => ({
        expense_name: line.expense_name.trim(),
        nature: line.nature,
        expenses_on: line.expenses_on,
        rate: Number(line.rate || 0),
        stage: Number(line.stage || 1),
        account_name: line.account_name.trim() || null,
        dr_cr: line.dr_cr,
        r_off: line.r_off,
        rcm_applicable: line.rcm_applicable,
        blocked_itc: line.blocked_itc,
      }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_expense_master) {
      setError("Desktop API is not available.");
      return;
    }
    if (!masterName.trim()) {
      setError("Expense name is required.");
      return;
    }
    const payload: Record<string, unknown> = {
      name: masterName.trim(),
      mandi_name: mandiName.trim() || null,
      lines: linesForSave(),
    };
    if (masterId) {
      payload.expense_master_id = masterId;
    }
    const response = await bridge.save_expense_master(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    setStatus("Data has been Successfully Saved");
    if (!masterId) {
      void bridge.list_expense_masters?.().then((list) => {
        const match = list?.expense_masters?.find(
          (row) => String(row.name ?? "").toLowerCase() === masterName.trim().toLowerCase(),
        );
        if (match) {
          setMasterId(String(match.expense_master_id ?? ""));
        }
      });
    }
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_expense_master || !masterId) {
      setError("Save the master first or load one with Find (F5) before delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_expense_master(masterId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  function newMaster() {
    setMasterId("");
    setMasterName("");
    setMandiName("");
    setLines([emptyExpenseLine()]);
    setStatus("");
    setError("");
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        formRef.current?.requestSubmit();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
      if (event.key === "F5") {
        event.preventDefault();
        void runFind();
      }
      if (event.key === "F6" && masterId) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <form
        ref={formRef}
        className="expense-master-screen"
        data-expense-master-form
        onSubmit={(event) => void save(event)}
      >
        <h2 className="expense-master-title">Expense Master</h2>

        <div className="expense-master-header">
          <label className="expense-master-field">
            <span>Expense Name</span>
            <input
              className="expense-master-input"
              data-enter-order={1}
              value={masterName}
              onChange={(event) => setMasterName(event.target.value)}
            />
          </label>
          <label className="expense-master-field">
            <span>Mandi Name</span>
            <input
              className="expense-master-input"
              data-enter-order={2}
              value={mandiName}
              onChange={(event) => setMandiName(event.target.value)}
            />
          </label>
          <div className="expense-master-header-actions">
            <button className="expense-master-btn" type="button" onClick={() => void runFind()}>
              Find (F5)
            </button>
            <button className="expense-master-btn" type="button" onClick={newMaster}>
              New
            </button>
          </div>
        </div>

        <div className="expense-master-actions">
          <button className="expense-master-btn expense-master-btn-save" type="submit">
            Save (F3)
          </button>
          <button className="expense-master-btn" type="button" onClick={onExit}>
            Cancel (F4)
          </button>
          <button
            className="expense-master-btn expense-master-btn-delete"
            disabled={!masterId}
            type="button"
            onClick={() => setDeleteOpen(true)}
          >
            Delete (F6)
          </button>
        </div>

        <div
          ref={gridRef}
          className="expense-master-grid-wrap"
          onKeyDown={handleGridEnter}
        >
          <table className="expense-master-grid">
            <thead>
              <tr>
                <th>SNo</th>
                <th>Expense Name</th>
                <th>Nature</th>
                <th>Expenses On</th>
                <th>Rate</th>
                <th>Stage</th>
                <th>Account Name</th>
                <th>Dr/Cr</th>
                <th>ROff</th>
                <th>RCM</th>
                <th>Blocked ITC</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`line-${index}`} data-grid-row>
                  <td className="expense-master-sno">{index + 1}</td>
                  <td>
                    <input
                      className="expense-master-cell-input"
                      value={line.expense_name}
                      onChange={(event) =>
                        updateLine(index, { expense_name: event.target.value })
                      }
                    />
                  </td>
                  <td>
                    <select
                      className="expense-master-cell-input"
                      value={line.nature}
                      onChange={(event) =>
                        updateLine(index, {
                          nature: event.target.value as ExpenseLine["nature"],
                        })
                      }
                    >
                      {EXPENSE_NATURES.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="expense-master-cell-input"
                      value={line.expenses_on}
                      onChange={(event) =>
                        updateLine(index, {
                          expenses_on: event.target.value as ExpenseLine["expenses_on"],
                        })
                      }
                    >
                      {EXPENSES_ON.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="expense-master-cell-input expense-master-rate"
                      inputMode="decimal"
                      step="0.001"
                      type="number"
                      value={line.rate}
                      onChange={(event) => updateLine(index, { rate: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="expense-master-cell-input expense-master-stage"
                      inputMode="numeric"
                      type="number"
                      value={line.stage}
                      onChange={(event) => updateLine(index, { stage: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="expense-master-cell-input"
                      list="expense-master-accounts"
                      value={line.account_name}
                      onChange={(event) =>
                        updateLine(index, { account_name: event.target.value })
                      }
                    />
                  </td>
                  <td>
                    <select
                      className="expense-master-cell-input"
                      value={line.dr_cr}
                      onChange={(event) =>
                        updateLine(index, {
                          dr_cr: event.target.value as ExpenseLine["dr_cr"],
                        })
                      }
                    >
                      {EXPENSE_DR_CR.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="expense-master-cell-input"
                      value={line.r_off}
                      onChange={(event) =>
                        updateLine(index, {
                          r_off: event.target.value as ExpenseLine["r_off"],
                        })
                      }
                    >
                      {EXPENSE_R_OFF.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="expense-master-cell-input"
                      value={line.rcm_applicable}
                      onChange={(event) =>
                        updateLine(index, { rcm_applicable: event.target.value })
                      }
                    >
                      <option value="No">No</option>
                      <option value="Yes">Yes</option>
                    </select>
                  </td>
                  <td>
                    <select
                      className="expense-master-cell-input"
                      value={line.blocked_itc}
                      onChange={(event) =>
                        updateLine(index, { blocked_itc: event.target.value })
                      }
                    >
                      <option value="No">No</option>
                      <option value="Yes">Yes</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <datalist id="expense-master-accounts">
            {accountNames.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </div>

        <footer className="expense-master-status">
          {error ? <span className="expense-master-error">{error}</span> : null}
          {!error && status ? <span className="expense-master-ok">{status}</span> : null}
        </footer>
      </form>

      {findOpen && (
        <div className="expense-master-find-overlay" role="presentation">
          <div className="expense-master-find-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Find Expense Master (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setFindOpen(false)}>
                ×
              </button>
            </header>
            <form
              className="expense-master-find-search"
              onSubmit={(event) => {
                event.preventDefault();
                void runFind(findQuery);
              }}
            >
              <input
                placeholder="Expense / mandi name"
                value={findQuery}
                onChange={(event) => {
                  setFindQuery(event.target.value);
                  void refreshFindList(event.target.value);
                }}
              />
              <button type="submit">Search</button>
            </form>
            <div className="expense-master-find-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Expense Name</th>
                    <th>Mandi</th>
                    <th>Lines</th>
                  </tr>
                </thead>
                <tbody>
                  {findRows.map((row) => (
                    <tr
                      key={String(row.expense_master_id)}
                      tabIndex={0}
                      onDoubleClick={() => applyRecord(row)}
                    >
                      <td>{String(row.name ?? "")}</td>
                      <td>{String(row.mandi_name ?? "")}</td>
                      <td>{Array.isArray(row.lines) ? row.lines.length : 0}</td>
                    </tr>
                  ))}
                  {!findRows.length && (
                    <tr>
                      <td colSpan={3}>No expense masters found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={masterName || "this expense master"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
