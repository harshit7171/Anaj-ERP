import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useFormEnterFlow } from "../../hooks/useFormEnterFlow";
import useFieldFocusHandlers from "../../hooks/useFieldFocusHandlers";
import {
  I_FORM_R_OFF,
  I_FORM_RATE_ON,
  blankIFormLines,
  type IFormExpenseLine,
} from "./constants";
import {
  buildItemRows,
  formatDateDdMmYyyy,
  type ItemPickerRow,
} from "./itemPicker";

type ApiResult = { ok: boolean; error?: string };

type IFormExpenseApi = {
  list_items?(): Promise<ApiResult & { items?: Record<string, unknown>[] }>;
  list_i_form_expense_defines?(commodity_id?: string): Promise<
    ApiResult & { defines?: Record<string, unknown>[] }
  >;
  get_i_form_expense_define?(
    commodity_id: string,
    effective_date: string,
  ): Promise<ApiResult & { define?: Record<string, unknown> }>;
  save_i_form_expense_define?(payload: Record<string, unknown>): Promise<
    ApiResult & { define?: Record<string, unknown> }
  >;
  delete_i_form_expense_define?(define_id: string): Promise<ApiResult>;
  find_accounts?(query?: string): Promise<
    ApiResult & { rows?: Record<string, unknown>[] }
  >;
};

function api(): IFormExpenseApi | undefined {
  return window.pywebview?.api as unknown as IFormExpenseApi | undefined;
}

function todayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function parseLines(raw: unknown, emptyRates: boolean): IFormExpenseLine[] {
  const skeleton = blankIFormLines();
  if (emptyRates || !Array.isArray(raw)) return skeleton;
  const byName = new Map<string, Record<string, unknown>>();
  for (const row of raw) {
    if (row && typeof row === "object") {
      const item = row as Record<string, unknown>;
      byName.set(String(item.expense_name ?? ""), item);
    }
  }
  return skeleton.map((line) => {
    const saved = byName.get(line.expense_name);
    if (!saved) return line;
    const rateNum = Number(saved.rate);
    const rateStr =
      saved.rate === undefined || saved.rate === null || saved.rate === ""
        ? ""
        : Number.isFinite(rateNum)
          ? String(rateNum)
          : String(saved.rate);
    return {
      expense_name: line.expense_name,
      display_name: String(saved.display_name ?? ""),
      rate: rateStr,
      rate_on: I_FORM_RATE_ON.includes(saved.rate_on as never)
        ? (saved.rate_on as IFormExpenseLine["rate_on"])
        : "A",
      account_name: String(saved.account_name ?? ""),
      round_off: I_FORM_R_OFF.includes(saved.round_off as never)
        ? (saved.round_off as IFormExpenseLine["round_off"])
        : "N",
    };
  });
}

export default function IFormExpenseScreen({ onExit }: { onExit(): void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const itemInputRef = useRef<HTMLInputElement>(null);

  const [itemRows, setItemRows] = useState<ItemPickerRow[]>([]);
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([]);
  const [defineIds, setDefineIds] = useState<Record<string, string>>({});
  const [itemPickerOpen, setItemPickerOpen] = useState(false);
  const [itemFilter, setItemFilter] = useState("");

  const [effectiveDate, setEffectiveDate] = useState(todayIso());
  const [detailsActive, setDetailsActive] = useState(false);

  const [dami, setDami] = useState("");
  const [damiOn, setDamiOn] = useState<(typeof I_FORM_RATE_ON)[number]>("A");
  const [damiROff, setDamiROff] = useState<(typeof I_FORM_R_OFF)[number]>("N");
  const [bonus, setBonus] = useState("");
  const [bonusROff, setBonusROff] = useState<(typeof I_FORM_R_OFF)[number]>("N");
  const [rdfKkf, setRdfKkf] = useState("");
  const [rdfROff, setRdfROff] = useState<(typeof I_FORM_R_OFF)[number]>("N");
  const [mktPct, setMktPct] = useState("");
  const [mktROff, setMktROff] = useState<(typeof I_FORM_R_OFF)[number]>("N");

  const [lines, setLines] = useState<IFormExpenseLine[]>(blankIFormLines());
  const [accountNames, setAccountNames] = useState<string[]>([]);

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [showOpen, setShowOpen] = useState(false);
  const [showRows, setShowRows] = useState<Record<string, unknown>[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useFormEnterFlow(formRef, true);
  useFieldFocusHandlers(formRef, true);

  useEffect(() => {
    const bridge = api();
    void bridge?.list_items?.().then(async (itemsResponse) => {
      if (!itemsResponse?.ok || !itemsResponse.items) return;
      const definesResponse = await bridge.list_i_form_expense_defines?.("");
      const dateByItem = new Map<string, string>();
      for (const row of definesResponse?.defines ?? []) {
        const id = String(row.commodity_id ?? "");
        const date = String(row.effective_date ?? "");
        if (id && date && !dateByItem.has(id)) {
          dateByItem.set(id, date);
        }
      }
      setItemRows(buildItemRows(itemsResponse.items, dateByItem));
    });
    void bridge?.find_accounts?.("").then((response) => {
      if (!response?.ok || !response.rows) return;
      const names = response.rows
        .map((row) => String(row.name ?? row.account_name ?? "").trim())
        .filter(Boolean);
      setAccountNames([...new Set(names)].sort((a, b) => a.localeCompare(b)));
    });
  }, []);

  const selectedLabels = useMemo(() => {
    const byId = new Map(itemRows.map((row) => [row.id, row.itemName]));
    return selectedItemIds.map((id) => byId.get(id) ?? id).filter(Boolean);
  }, [itemRows, selectedItemIds]);

  const itemFieldValue = itemPickerOpen ? itemFilter : selectedLabels.join(", ");

  const filteredItemRows = useMemo(() => {
    const q = itemFilter.trim().toLowerCase();
    if (!q) return itemRows;
    return itemRows.filter((row) => {
      const hay = [row.itemName, row.itemGroup, row.itemUnit, row.savedDate]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [itemRows, itemFilter]);

  const hasSavedDefine = selectedItemIds.some((id) => Boolean(defineIds[id]));

  function clearLoadedDetails() {
    setDefineIds({});
    setDami("");
    setDamiOn("A");
    setDamiROff("N");
    setBonus("");
    setBonusROff("N");
    setRdfKkf("");
    setRdfROff("N");
    setMktPct("");
    setMktROff("N");
    setLines(blankIFormLines());
    setDetailsActive(false);
    setStatus("");
    setError("");
  }

  function toggleItemSelection(id: string) {
    setSelectedItemIds((prev) => {
      const set = new Set(prev);
      if (set.has(id)) {
        set.delete(id);
      } else {
        set.add(id);
      }
      return [...set];
    });
    clearLoadedDetails();
  }

  function applyDefineData(row: Record<string, unknown>) {
    const defineId = String(row.define_id ?? "");
    setEffectiveDate(String(row.effective_date ?? todayIso()));
    setDami(String(row.dami ?? ""));
    setDamiOn(
      I_FORM_RATE_ON.includes(row.dami_on as never)
        ? (row.dami_on as typeof damiOn)
        : "A",
    );
    setDamiROff(
      I_FORM_R_OFF.includes(row.dami_r_off as never)
        ? (row.dami_r_off as typeof damiROff)
        : "N",
    );
    setBonus(String(row.bonus ?? ""));
    setBonusROff(
      I_FORM_R_OFF.includes(row.bonus_r_off as never)
        ? (row.bonus_r_off as typeof bonusROff)
        : "N",
    );
    setRdfKkf(String(row.rdf_kkf_percent ?? ""));
    setRdfROff(
      I_FORM_R_OFF.includes(row.rdf_r_off as never)
        ? (row.rdf_r_off as typeof rdfROff)
        : "N",
    );
    setMktPct(String(row.mkt_percent ?? ""));
    setMktROff(
      I_FORM_R_OFF.includes(row.mkt_r_off as never)
        ? (row.mkt_r_off as typeof mktROff)
        : "N",
    );
    setLines(parseLines(row.lines, !defineId));
    setDetailsActive(true);
    setError("");
    return defineId;
  }

  function applyDefineFromShow(row: Record<string, unknown>) {
    const commodityId = String(row.commodity_id ?? "");
    if (commodityId) {
      setSelectedItemIds([commodityId]);
    }
    const defineId = applyDefineData(row);
    setDefineIds(defineId && commodityId ? { [commodityId]: defineId } : {});
    setItemPickerOpen(false);
    setShowOpen(false);
    setStatus(
      defineId
        ? "Record loaded — you can edit and save (F3)."
        : "No saved record for this item and date — enter details and save.",
    );
  }

  async function refreshDefineIdsForSelection(ids: string[], date: string) {
    const bridge = api();
    if (!bridge?.get_i_form_expense_define) return {};
    const next: Record<string, string> = {};
    for (const id of ids) {
      const response = await bridge.get_i_form_expense_define(id, date);
      const defineId = String(response?.define?.define_id ?? "");
      if (defineId) {
        next[id] = defineId;
      }
    }
    return next;
  }

  async function loadForFirstSelected() {
    if (!selectedItemIds.length) {
      setError("Select one or more items from the list.");
      return;
    }
    const bridge = api();
    if (!bridge?.get_i_form_expense_define) {
      setError("Desktop API is not available.");
      return;
    }
    const primaryId = selectedItemIds[0];
    const response = await bridge.get_i_form_expense_define(primaryId, effectiveDate);
    if (!response?.ok) {
      setError(response?.error ?? "Load failed.");
      return;
    }
    if (response.define) {
      applyDefineData({ ...response.define, commodity_id: primaryId });
    }
    const idsMap = await refreshDefineIdsForSelection(selectedItemIds, effectiveDate);
    setDefineIds(idsMap);
    setItemPickerOpen(false);
    if (selectedItemIds.length > 1) {
      setStatus(
        `Loaded from ${selectedLabels[0] ?? "first item"}. Save (F3) applies the same setup to ${selectedItemIds.length} selected items.`,
      );
    } else {
      setStatus(
        idsMap[primaryId]
          ? "Record loaded — you can edit and save (F3)."
          : "No saved record for this item and date — enter details and save.",
      );
    }
  }

  async function openShowList() {
    const bridge = api();
    if (!bridge?.list_i_form_expense_defines) {
      setError("Desktop API is not available.");
      return;
    }
    const filterId = selectedItemIds.length === 1 ? selectedItemIds[0] : "";
    const response = await bridge.list_i_form_expense_defines(filterId);
    if (!response?.ok) {
      setError(response?.error ?? "Could not list records.");
      return;
    }
    setShowRows(response.defines ?? []);
    setShowOpen(true);
  }

  async function runShow() {
    if (selectedItemIds.length && effectiveDate) {
      await loadForFirstSelected();
      return;
    }
    await openShowList();
  }

  function buildSavePayload(commodityId: string): Record<string, unknown> {
    return {
      define_id: defineIds[commodityId] || undefined,
      commodity_id: commodityId,
      effective_date: effectiveDate,
      dami: dami.trim() || null,
      dami_on: damiOn,
      dami_r_off: damiROff,
      bonus: bonus.trim() || null,
      bonus_r_off: bonusROff,
      rdf_kkf_percent: rdfKkf.trim() || null,
      rdf_r_off: rdfROff,
      mkt_percent: mktPct.trim() || null,
      mkt_r_off: mktROff,
      lines: lines.map((line) => ({
        expense_name: line.expense_name,
        display_name: line.display_name.trim(),
        rate: line.rate.trim() === "" ? 0 : Number(line.rate),
        rate_on: line.rate_on,
        account_name: line.account_name.trim() || null,
        round_off: line.round_off,
      })),
    };
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!detailsActive) {
      setError("Select item(s) and press Show (F5) before saving.");
      return;
    }
    const bridge = api();
    if (!bridge?.save_i_form_expense_define) {
      setError("Desktop API is not available.");
      return;
    }
    if (!selectedItemIds.length) {
      setError("Select at least one item.");
      return;
    }
    if (!effectiveDate) {
      setError("Date is required.");
      return;
    }
    const nextDefineIds = { ...defineIds };
    for (const commodityId of selectedItemIds) {
      const response = await bridge.save_i_form_expense_define(buildSavePayload(commodityId));
      if (!response?.ok) {
        setError(response?.error ?? "Save failed.");
        return;
      }
      const saved = response.define as Record<string, unknown> | undefined;
      if (saved?.define_id) {
        nextDefineIds[commodityId] = String(saved.define_id);
      }
    }
    setDefineIds(nextDefineIds);
    setDetailsActive(true);
    setStatus(
      selectedItemIds.length > 1
        ? `Data saved for ${selectedItemIds.length} items.`
        : "Data has been Successfully Saved",
    );
  }

  function updateLine(index: number, patch: Partial<IFormExpenseLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  async function confirmDelete() {
    const bridge = api();
    const idsToDelete = selectedItemIds
      .map((id) => defineIds[id])
      .filter(Boolean);
    if (!bridge?.delete_i_form_expense_define || !idsToDelete.length) {
      setError("Load saved record(s) with Show (F5) before delete.");
      setDeleteOpen(false);
      return;
    }
    for (const defineId of idsToDelete) {
      const response = await bridge.delete_i_form_expense_define(defineId);
      if (!response?.ok) {
        setError(response?.error ?? "Delete failed.");
        setDeleteOpen(false);
        return;
      }
    }
    setDeleteOpen(false);
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
      if (event.key === "F5") {
        event.preventDefault();
        void runShow();
      }
      if (event.key === "F6" && hasSavedDefine) {
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
        className="iform-expense-screen"
        data-i-form-expense-form
        onSubmit={(event) => void save(event)}
      >
        <div className="iform-expense-top">
          <h2 className="iform-expense-title">Define I Form Expense</h2>
          <div className="iform-expense-actions">
            <button className="iform-expense-btn" type="button" onClick={() => void runShow()}>
              Show (F5)
            </button>
            <button className="iform-expense-btn iform-expense-btn-save" type="submit">
              Save (F3)
            </button>
            <button className="iform-expense-btn" type="button" onClick={onExit}>
              Cancel (F4)
            </button>
            <button
              className="iform-expense-btn iform-expense-btn-delete"
              disabled={!hasSavedDefine}
              type="button"
              onClick={() => setDeleteOpen(true)}
            >
              Delete (F6)
            </button>
          </div>
        </div>

        {!detailsActive && (
          <p className="iform-expense-hint" role="status">
            Click <strong>Item</strong>, tick Bardana / Paddy / Wheat (multiple allowed), then{" "}
            <strong>Show (F5)</strong> to load or enter expense rates.
          </p>
        )}

        <div className="iform-expense-params iform-expense-params-item-row">
          <div className="iform-expense-item-picker-wrap">
            <label className="iform-expense-param iform-expense-item-select">
              <span>Item</span>
              <input
                ref={itemInputRef}
                className="iform-expense-input iform-expense-item-field"
                data-enter-order={1}
                readOnly={!itemPickerOpen}
                value={itemFieldValue}
                onChange={(event) => setItemFilter(event.target.value)}
                onFocus={() => {
                  setItemPickerOpen(true);
                  setItemFilter("");
                }}
              />
            </label>
            {itemPickerOpen && (
              <div className="iform-expense-item-picker" role="listbox" aria-multiselectable>
                <div className="iform-expense-item-picker-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th aria-label="Select" />
                      <th>Item Name</th>
                      <th>Item Group</th>
                      <th>Item Unit</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItemRows.map((row) => {
                      const checked = selectedItemIds.includes(row.id);
                      return (
                        <tr
                          key={row.id}
                          className={checked ? "iform-expense-item-row-selected" : undefined}
                          onClick={() => toggleItemSelection(row.id)}
                        >
                          <td onClick={(event) => event.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleItemSelection(row.id)}
                            />
                          </td>
                          <td>{row.itemName}</td>
                          <td>{row.itemGroup}</td>
                          <td>{row.itemUnit}</td>
                          <td>{row.savedDate ? formatDateDdMmYyyy(row.savedDate) : ""}</td>
                        </tr>
                      );
                    })}
                    {!filteredItemRows.length && (
                      <tr>
                        <td colSpan={5}>No items match.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
                </div>
                <div className="iform-expense-item-picker-actions">
                  <span>
                    {selectedItemIds.length
                      ? `${selectedItemIds.length} item(s) selected`
                      : "Select one or more items"}
                  </span>
                  <button type="button" onClick={() => setItemPickerOpen(false)}>
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
          <label className="iform-expense-param">
            <span>Date(s)</span>
            <input
              className="iform-expense-input"
              data-enter-order={2}
              type="date"
              value={effectiveDate}
              onChange={(event) => {
                setEffectiveDate(event.target.value);
                if (detailsActive) {
                  clearLoadedDetails();
                }
              }}
            />
          </label>
        </div>

        <fieldset className="iform-expense-params" disabled={!detailsActive}>
          <div className="iform-expense-param-group">
            <label className="iform-expense-param">
              <span>Dami</span>
              <input
                className="iform-expense-input iform-expense-input-short"
                value={dami}
                onChange={(event) => setDami(event.target.value)}
              />
            </label>
            <label className="iform-expense-param">
              <span>Dami On</span>
              <select
                className="iform-expense-input iform-expense-input-short"
                value={damiOn}
                onChange={(event) => setDamiOn(event.target.value as typeof damiOn)}
              >
                {I_FORM_RATE_ON.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="iform-expense-param">
              <span>ROff</span>
              <select
                className="iform-expense-input iform-expense-input-short"
                value={damiROff}
                onChange={(event) => setDamiROff(event.target.value as typeof damiROff)}
              >
                {I_FORM_R_OFF.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="iform-expense-param-group">
            <label className="iform-expense-param">
              <span>Bonus</span>
              <input
                className="iform-expense-input iform-expense-input-short"
                value={bonus}
                onChange={(event) => setBonus(event.target.value)}
              />
            </label>
            <label className="iform-expense-param">
              <span>ROff</span>
              <select
                className="iform-expense-input iform-expense-input-short"
                value={bonusROff}
                onChange={(event) => setBonusROff(event.target.value as typeof bonusROff)}
              >
                {I_FORM_R_OFF.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="iform-expense-param-group">
            <label className="iform-expense-param">
              <span>RDF / KKF %</span>
              <input
                className="iform-expense-input iform-expense-input-short"
                value={rdfKkf}
                onChange={(event) => setRdfKkf(event.target.value)}
              />
            </label>
            <label className="iform-expense-param">
              <span>ROff</span>
              <select
                className="iform-expense-input iform-expense-input-short"
                value={rdfROff}
                onChange={(event) => setRdfROff(event.target.value as typeof rdfROff)}
              >
                {I_FORM_R_OFF.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="iform-expense-param-group">
            <label className="iform-expense-param">
              <span>Mkt %</span>
              <input
                className="iform-expense-input iform-expense-input-short"
                value={mktPct}
                onChange={(event) => setMktPct(event.target.value)}
              />
            </label>
            <label className="iform-expense-param">
              <span>ROff</span>
              <select
                className="iform-expense-input iform-expense-input-short"
                value={mktROff}
                onChange={(event) => setMktROff(event.target.value as typeof mktROff)}
              >
                {I_FORM_R_OFF.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        {!detailsActive && selectedItemIds.length > 0 && (
          <p className="iform-expense-hint iform-expense-hint-item">
            Selected: <strong>{selectedLabels.join(", ")}</strong> — press Show (F5).
          </p>
        )}

        <div className="iform-expense-grid-wrap">
          <table className="iform-expense-grid">
            <thead>
              <tr>
                <th>Expense Name</th>
                <th>Disp. Name</th>
                <th>Rate</th>
                <th>Rate On</th>
                <th>Account Name</th>
                <th>Round Off</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr
                  key={line.expense_name}
                  className={!detailsActive ? "iform-expense-row-pending" : undefined}
                >
                  <td className="iform-expense-name-cell">{line.expense_name}</td>
                  <td>
                    <input
                      className="iform-expense-cell-input"
                      disabled={!detailsActive}
                      placeholder={detailsActive ? "" : "—"}
                      value={line.display_name}
                      onChange={(event) =>
                        updateLine(index, { display_name: event.target.value })
                      }
                    />
                  </td>
                  <td>
                    <input
                      className="iform-expense-cell-input iform-expense-rate"
                      disabled={!detailsActive}
                      inputMode="decimal"
                      placeholder={detailsActive ? "0.000" : "—"}
                      type="text"
                      value={line.rate}
                      onChange={(event) => updateLine(index, { rate: event.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      className="iform-expense-cell-input"
                      disabled={!detailsActive}
                      value={line.rate_on}
                      onChange={(event) =>
                        updateLine(index, {
                          rate_on: event.target.value as IFormExpenseLine["rate_on"],
                        })
                      }
                    >
                      {I_FORM_RATE_ON.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="iform-expense-cell-input"
                      disabled={!detailsActive}
                      list={detailsActive ? "iform-expense-accounts" : undefined}
                      placeholder={detailsActive ? "" : "—"}
                      value={line.account_name}
                      onChange={(event) =>
                        updateLine(index, { account_name: event.target.value })
                      }
                    />
                  </td>
                  <td>
                    <select
                      className="iform-expense-cell-input"
                      disabled={!detailsActive}
                      value={line.round_off}
                      onChange={(event) =>
                        updateLine(index, {
                          round_off: event.target.value as IFormExpenseLine["round_off"],
                        })
                      }
                    >
                      {I_FORM_R_OFF.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <datalist id="iform-expense-accounts">
            {accountNames.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </div>

        <footer className="iform-expense-status">
          {error ? <span className="iform-expense-error">{error}</span> : null}
          {!error && status ? <span className="iform-expense-ok">{status}</span> : null}
        </footer>
      </form>

      {showOpen && (
        <div className="iform-expense-show-overlay" role="presentation">
          <div className="iform-expense-show-panel" role="dialog" aria-modal="true">
            <header>
              <strong>Show — all I Form expense records (F5)</strong>
              <button type="button" aria-label="Close" onClick={() => setShowOpen(false)}>
                ×
              </button>
            </header>
            <p className="iform-expense-show-help">
              Double-click a row to load item, date, Dami/Mkt settings, and grid rates.
            </p>
            <div className="iform-expense-show-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {showRows.map((row) => (
                    <tr
                      key={String(row.define_id)}
                      tabIndex={0}
                      onDoubleClick={() => applyDefineFromShow(row)}
                    >
                      <td>{String(row.item_name ?? "")}</td>
                      <td>{formatDateDdMmYyyy(String(row.effective_date ?? ""))}</td>
                    </tr>
                  ))}
                  {!showRows.length && (
                    <tr>
                      <td colSpan={2}>No saved records yet.</td>
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
        recordLabel={selectedLabels.join(", ") || "selected items"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
