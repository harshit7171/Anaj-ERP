import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import { buildItemRows, type ItemPickerRow } from "../i-form-expense-define/itemPicker";
import {
  ddMmYyyyToIso,
  emptyStockLine,
  isoToday,
  isoToDdMmYyyy,
  parseStockLines,
  type StockEntryKind,
  type StockLine,
  withTrailingBlankLine,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type StockEntryApi = {
  list_items?(): Promise<ApiResult & { items?: Record<string, unknown>[] }>;
  find_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  get_stock_entry_master?(args: {
    stock_entry_id?: string;
    entry_kind?: string;
    entry_date?: string;
    search_item?: string;
  }): Promise<ApiResult & { stock_entry?: Record<string, unknown> }>;
  save_stock_entry_master?(payload: Record<string, unknown>): Promise<
    ApiResult & { stock_entry?: Record<string, unknown> }
  >;
  delete_stock_entry_master?(stock_entry_id: string): Promise<ApiResult>;
};

function api(): StockEntryApi | undefined {
  return window.pywebview?.api as unknown as StockEntryApi | undefined;
}

function matchesFilters(line: StockLine, filters: string[]): boolean {
  const hay = [line.item_name, line.unit, line.account_name, line.qty, line.weight]
    .join(" ")
    .toLowerCase();
  return filters.every((filter) => !filter.trim() || hay.includes(filter.trim().toLowerCase()));
}

export default function StockEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const entryKind: StockEntryKind = mode === "add" ? "opening" : "closing";
  const title = mode === "add" ? "Opening Stock Entry" : "Closing Stock Entry";

  const formRef = useRef<HTMLFormElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const [stockEntryId, setStockEntryId] = useState("");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [searchItem, setSearchItem] = useState("");
  const [showOpening, setShowOpening] = useState(false);
  const [filters, setFilters] = useState(["", "", "", ""]);
  const [lines, setLines] = useState<StockLine[]>([emptyStockLine()]);

  const [itemRows, setItemRows] = useState<ItemPickerRow[]>([]);
  const [accountRows, setAccountRows] = useState<Record<string, unknown>[]>([]);
  const [itemPickerIndex, setItemPickerIndex] = useState<number | null>(null);
  const [accountPickerIndex, setAccountPickerIndex] = useState<number | null>(null);

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => withTrailingBlankLine(prev));
    return false;
  });

  useEffect(() => {
    void api()?.list_items?.().then((response) => {
      if (!response?.ok || !response.items) return;
      setItemRows(buildItemRows(response.items, new Map()));
    });
    void api()?.find_accounts?.("").then((response) => {
      if (!response?.ok || !response.rows) return;
      setAccountRows(response.rows);
    });
  }, []);

  function applyRecord(record: Record<string, unknown>) {
    setStockEntryId(String(record.stock_entry_id ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setSearchItem(String(record.search_item ?? ""));
    setShowOpening(Boolean(record.show_opening));
    setFilters([
      String(record.filter1 ?? ""),
      String(record.filter2 ?? ""),
      String(record.filter3 ?? ""),
      String(record.filter4 ?? ""),
    ]);
    setLines(withTrailingBlankLine(parseStockLines(record.lines)));
    setStatus("Stock entry loaded.");
    setError("");
  }

  async function runShow() {
    setError("");
    const bridge = api();
    if (!bridge?.get_stock_entry_master) {
      setError("Desktop API is not available.");
      return;
    }
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const response = await bridge.get_stock_entry_master({
      stock_entry_id: stockEntryId || undefined,
      entry_kind: entryKind,
      entry_date: isoDate,
      search_item: searchItem.trim(),
    });
    if (!response?.ok || !response.stock_entry) {
      setError(response?.error ?? "No stock entry found for this date.");
      return;
    }
    applyRecord(response.stock_entry);
  }

  function updateLine(index: number, patch: Partial<StockLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => (i === index ? { ...line, ...patch } : line));
      return withTrailingBlankLine(next);
    });
  }

  function selectItem(index: number, row: ItemPickerRow) {
    updateLine(index, {
      commodity_id: row.id,
      item_name: row.itemName,
      unit: row.itemUnit || lines[index]?.unit || "",
    });
    setItemPickerIndex(null);
  }

  function selectAccount(index: number, row: Record<string, unknown>) {
    updateLine(index, {
      account_id: String(row.account_id ?? ""),
      account_name: String(row.name ?? row.account_name ?? ""),
    });
    setAccountPickerIndex(null);
  }

  function linesForSave(): Record<string, unknown>[] {
    return lines
      .filter((line) => line.item_name.trim() || line.commodity_id)
      .map((line) => ({
        line_id: line.line_id || undefined,
        commodity_id: line.commodity_id || null,
        item_name: line.item_name.trim(),
        unit: line.unit.trim() || null,
        account_id: line.account_id || null,
        account_name: line.account_name.trim() || null,
        qty: line.qty.trim() || null,
        weight: line.weight.trim() || null,
        rate: line.rate.trim() || null,
        amount: line.amount.trim() || null,
        mm: line.mm.trim() || null,
      }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const bridge = api();
    if (!bridge?.save_stock_entry_master) {
      setError("Desktop API is not available.");
      return;
    }
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    if (!isoDate) {
      setError("Entry date is required.");
      return;
    }
    const payload: Record<string, unknown> = {
      stock_entry_id: stockEntryId || undefined,
      entry_kind: entryKind,
      entry_date: isoDate,
      search_item: searchItem.trim() || null,
      show_opening: showOpening,
      filter1: filters[0] || null,
      filter2: filters[1] || null,
      filter3: filters[2] || null,
      filter4: filters[3] || null,
      lines: linesForSave(),
    };
    const response = await bridge.save_stock_entry_master(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.stock_entry) {
      applyRecord(response.stock_entry);
    }
    setStatus("Data has been Successfully Saved");
  }

  async function confirmDelete() {
    const bridge = api();
    if (!bridge?.delete_stock_entry_master || !stockEntryId) {
      setError("Nothing to delete.");
      setDeleteOpen(false);
      return;
    }
    const response = await bridge.delete_stock_entry_master(stockEntryId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
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
      if (event.key === "F5" && mode === "modify") {
        event.preventDefault();
        void runShow();
      }
      if (event.key === "F6" && mode === "modify" && stockEntryId) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const visibleLines = lines
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => matchesFilters(line, filters));

  return (
    <>
      <form
        ref={formRef}
        className="stock-entry-screen"
        data-stock-entry-form
        data-stock-entry-kind={entryKind}
        onSubmit={(event) => void save(event)}
      >
        <div className="stock-entry-toolbar">
          <div className="stock-entry-toolbar-left">
            {mode === "add" ? (
              <>
                <label className="stock-entry-date-label">
                  Opening Date
                  <input
                    className="stock-entry-input"
                    type="date"
                    value={entryDate}
                    onChange={(event) => setEntryDate(event.target.value)}
                  />
                </label>
                <label className="stock-entry-check">
                  <input
                    checked={showOpening}
                    type="checkbox"
                    onChange={(event) => setShowOpening(event.target.checked)}
                  />
                  Show Opening
                </label>
              </>
            ) : (
              <>
                <label className="stock-entry-date-label">
                  Date
                  <input
                    className="stock-entry-input stock-entry-date-text"
                    placeholder="DD/MM/YYYY"
                    value={entryDate}
                    onChange={(event) => setEntryDate(event.target.value)}
                  />
                </label>
                <label className="stock-entry-search-label">
                  Search Item Here
                  <input
                    className="stock-entry-input stock-entry-search-input"
                    value={searchItem}
                    onChange={(event) => setSearchItem(event.target.value)}
                  />
                </label>
              </>
            )}
          </div>
          <div className="stock-entry-toolbar-actions">
            {mode === "modify" && (
              <>
                <button className="stock-entry-btn" type="button" onClick={() => void runShow()}>
                  Show (F5)
                </button>
                <button
                  className="stock-entry-btn stock-entry-btn-delete"
                  disabled={!stockEntryId}
                  type="button"
                  onClick={() => setDeleteOpen(true)}
                >
                  Delete (F6)
                </button>
              </>
            )}
            <button className="stock-entry-btn stock-entry-btn-save" type="submit">
              Save (F3)
            </button>
            <button className="stock-entry-btn" type="button" onClick={onExit}>
              Cancel (F4)
            </button>
          </div>
        </div>

        {mode === "add" && (
          <div className="stock-entry-filters">
            {filters.map((value, filterIndex) => (
              <input
                key={filterIndex}
                className="stock-entry-filter-input"
                value={value}
                onChange={(event) => {
                  const next = [...filters];
                  next[filterIndex] = event.target.value;
                  setFilters(next);
                }}
              />
            ))}
          </div>
        )}

        <div
          ref={gridRef}
          className="stock-entry-grid-wrap"
          onKeyDown={handleGridEnter}
        >
          <table className="stock-entry-grid">
            <thead>
              <tr>
                <th />
                <th>Item</th>
                <th>Unit</th>
                <th>Account Name</th>
                <th>Qty</th>
                <th>Weight</th>
                {mode === "modify" ? <th>Rate</th> : null}
                <th>Amount</th>
                {mode === "add" ? <th>Mm</th> : null}
              </tr>
            </thead>
            <tbody>
              {visibleLines.map(({ line, index }) => (
                <tr key={`${index}-${line.line_id || "new"}`}>
                  <td className="stock-entry-sno">{index + 1}</td>
                  <td className="stock-entry-item-cell">
                    <input
                      className="stock-entry-cell-input"
                      value={line.item_name}
                      onChange={(event) => {
                        const value = event.target.value;
                        updateLine(index, { item_name: value });
                        const match = itemRows.find((row) =>
                          row.itemName.toLowerCase().startsWith(value.toLowerCase()),
                        );
                        if (value && match) {
                          setItemPickerIndex(index);
                        } else if (!value) {
                          setItemPickerIndex(null);
                        }
                      }}
                      onFocus={() => setItemPickerIndex(index)}
                    />
                    {itemPickerIndex === index && (
                      <div className="stock-entry-item-picker">
                        <div className="stock-entry-picker-head">ItName</div>
                        <ul>
                          {itemRows
                            .filter((row) =>
                              line.item_name
                                ? row.itemName
                                    .toLowerCase()
                                    .includes(line.item_name.toLowerCase())
                                : true,
                            )
                            .slice(0, 12)
                            .map((row) => (
                              <li key={row.id}>
                                <button type="button" onClick={() => selectItem(index, row)}>
                                  {row.itemName}
                                </button>
                              </li>
                            ))}
                        </ul>
                      </div>
                    )}
                  </td>
                  <td>
                    <input
                      className="stock-entry-cell-input"
                      value={line.unit}
                      onChange={(event) => updateLine(index, { unit: event.target.value })}
                    />
                  </td>
                  <td className="stock-entry-account-cell">
                    <input
                      className="stock-entry-cell-input"
                      value={line.account_name}
                      onChange={(event) => {
                        updateLine(index, { account_name: event.target.value });
                        setAccountPickerIndex(index);
                      }}
                      onFocus={() => setAccountPickerIndex(index)}
                    />
                    {accountPickerIndex === index && (
                      <div className="stock-entry-account-picker">
                        <div className="stock-entry-picker-head">Party</div>
                        <ul>
                          {accountRows
                            .filter((row) => {
                              const name = String(row.name ?? row.account_name ?? "");
                              return line.account_name
                                ? name.toLowerCase().includes(line.account_name.toLowerCase())
                                : true;
                            })
                            .slice(0, 12)
                            .map((row) => {
                              const name = String(row.name ?? row.account_name ?? "");
                              const id = String(row.account_id ?? name);
                              return (
                                <li key={id}>
                                  <button type="button" onClick={() => selectAccount(index, row)}>
                                    {name}
                                  </button>
                                </li>
                              );
                            })}
                        </ul>
                      </div>
                    )}
                  </td>
                  <td>
                    <input
                      className="stock-entry-cell-input stock-entry-num"
                      inputMode="decimal"
                      value={line.qty}
                      onChange={(event) => updateLine(index, { qty: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="stock-entry-cell-input stock-entry-num"
                      inputMode="decimal"
                      value={line.weight}
                      onChange={(event) => updateLine(index, { weight: event.target.value })}
                    />
                  </td>
                  {mode === "modify" ? (
                    <td>
                      <input
                        className="stock-entry-cell-input stock-entry-num"
                        inputMode="decimal"
                        value={line.rate}
                        onChange={(event) => {
                          const rate = event.target.value;
                          const weight = Number(line.weight || 0);
                          const amount =
                            weight && rate ? String(Number(rate) * weight) : line.amount;
                          updateLine(index, { rate, amount });
                        }}
                      />
                    </td>
                  ) : null}
                  <td>
                    <input
                      className="stock-entry-cell-input stock-entry-num"
                      inputMode="decimal"
                      value={line.amount}
                      onChange={(event) => updateLine(index, { amount: event.target.value })}
                    />
                  </td>
                  {mode === "add" ? (
                    <td>
                      <input
                        className="stock-entry-cell-input stock-entry-num"
                        value={line.mm}
                        onChange={(event) => updateLine(index, { mm: event.target.value })}
                      />
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <footer className="stock-entry-status">
          {error ? <span className="stock-entry-error">{error}</span> : null}
          {!error && status ? <span className="stock-entry-ok">{status}</span> : null}
        </footer>
      </form>

      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={`${title} on ${entryDate}`}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
